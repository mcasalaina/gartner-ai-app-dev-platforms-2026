import {
  BrowserAuthError,
  BrowserAuthErrorCodes,
  CacheLookupPolicy,
  InteractionRequiredAuthError,
  PublicClientApplication,
  type AccountInfo,
  type AuthenticationResult,
} from '@azure/msal-browser'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { AuthContext, type AuthValue } from './authContext'

const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID ?? ''
const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID ?? ''
const apiScope = import.meta.env.VITE_API_SCOPE ?? ''

const configurationError =
  tenantId && clientId && apiScope
    ? null
    : 'Authentication is not configured. Set VITE_ENTRA_TENANT_ID, VITE_ENTRA_CLIENT_ID, and VITE_API_SCOPE.'

const authRequest = { scopes: apiScope ? [apiScope] : [] }
const msal = new PublicClientApplication({
  auth: {
    clientId: clientId || '00000000-0000-0000-0000-000000000000',
    authority: `https://login.microsoftonline.com/${tenantId || 'organizations'}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
  },
})

function rolesFor(account: AccountInfo | null): string[] {
  const claims = account?.idTokenClaims as { roles?: string[] } | undefined
  return claims?.roles ?? []
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<AccountInfo | null>(null)
  const [initializing, setInitializing] = useState(true)
  const [initializationError, setInitializationError] = useState<string | null>(null)
  const tokenRequestRef = useRef<Promise<string> | null>(null)

  useEffect(() => {
    let active = true
    void (async () => {
      try {
        await msal.initialize()
        const redirectResult = await msal.handleRedirectPromise()
        const selected = redirectResult?.account ?? msal.getAllAccounts()[0] ?? null
        if (active) {
          msal.setActiveAccount(selected)
          setAccount(selected)
        }
      } catch (reason) {
        if (active) {
          setInitializationError(
            reason instanceof Error ? reason.message : 'Authentication initialization failed.',
          )
        }
      } finally {
        if (active) {
          setInitializing(false)
        }
      }
    })()
    return () => {
      active = false
    }
  }, [])

  const signIn = useCallback(async () => {
    if (configurationError) {
      throw new Error(configurationError)
    }
    await msal.loginRedirect(authRequest)
  }, [])

  const signOut = useCallback(async () => {
    if (account) {
      await msal.logoutRedirect({
        account,
        postLogoutRedirectUri: window.location.origin,
      })
    }
    setAccount(null)
  }, [account])

  const getAccessToken = useCallback(async () => {
    if (!account) {
      throw new Error('Sign in is required.')
    }

    if (tokenRequestRef.current) {
      return tokenRequestRef.current
    }

    const request = {
      ...authRequest,
      account,
      loginHint: account.username,
    }
    const tokenRequest = (async () => {
      let result: AuthenticationResult
      try {
        result = await msal.acquireTokenSilent({
          ...request,
          cacheLookupPolicy: CacheLookupPolicy.AccessTokenAndRefreshToken,
        })
      } catch (reason) {
        const timedOut = reason instanceof BrowserAuthError
          && reason.errorCode === BrowserAuthErrorCodes.timedOut
        if (!(reason instanceof InteractionRequiredAuthError) && !timedOut) {
          throw reason
        }
        try {
          result = await msal.acquireTokenPopup(request)
        } catch {
          throw new Error(
            'Your Microsoft sign-in session needs attention. Complete the sign-in window, then try again.',
          )
        }
      }

      return result.accessToken
    })()

    tokenRequestRef.current = tokenRequest
    try {
      return await tokenRequest
    } finally {
      if (tokenRequestRef.current === tokenRequest) {
        tokenRequestRef.current = null
      }
    }
  }, [account])

  const value = useMemo<AuthValue>(
    () => {
      const roles = rolesFor(account)
      const isAdmin = roles.includes('BankServicing.Admin')
      return {
        account,
        initializing,
        configurationError: configurationError ?? initializationError,
        isReviewer: isAdmin || roles.includes('BankServicing.ContentReviewer'),
        isAdmin,
        signIn,
        signOut,
        getAccessToken,
      }
    },
    [account, getAccessToken, initializationError, initializing, signIn, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
