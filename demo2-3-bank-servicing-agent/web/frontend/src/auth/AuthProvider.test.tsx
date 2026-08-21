import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StrictMode, useState, type ComponentType, type ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => {
  class MockInteractionRequiredAuthError extends Error {}
  class MockBrowserAuthError extends Error {
    readonly errorCode: string

    constructor(errorCode: string) {
      super(errorCode)
      this.errorCode = errorCode
    }
  }

  return {
    MockBrowserAuthError,
    MockInteractionRequiredAuthError,
    configuration: undefined as unknown,
    initialize: vi.fn(),
    handleRedirectPromise: vi.fn(),
    getAllAccounts: vi.fn(),
    setActiveAccount: vi.fn(),
    loginRedirect: vi.fn(),
    logoutRedirect: vi.fn(),
    acquireTokenSilent: vi.fn(),
    acquireTokenPopup: vi.fn(),
  }
})

vi.mock('@azure/msal-browser', () => ({
  BrowserAuthError: mocks.MockBrowserAuthError,
  BrowserAuthErrorCodes: {
    noTokenRequestCacheError: 'no_token_request_cache_error',
    timedOut: 'timed_out',
  },
  CacheLookupPolicy: { AccessTokenAndRefreshToken: 'access-token-and-refresh-token' },
  InteractionRequiredAuthError: mocks.MockInteractionRequiredAuthError,
  PublicClientApplication: vi.fn(function PublicClientApplication(configuration: unknown) {
    mocks.configuration = configuration
    return mocks
  }),
}))

type AuthProviderComponent = ComponentType<{ children: ReactNode }>
type UseAuth = typeof import('./authContext')['useAuth']

let AuthProvider: AuthProviderComponent
let useAuth: UseAuth

function Consumer() {
  const auth = useAuth()
  const [error, setError] = useState<string>()

  if (auth.initializing) {
    return <p>Initializing</p>
  }

  return (
    <>
      <button type="button" onClick={() => void auth.signIn().catch((reason: Error) => setError(reason.message))}>
        Sign in
      </button>
      {auth.account ? (
        <>
          <button type="button" onClick={() => void auth.signOut()}>Sign out</button>
          <button
            type="button"
            onClick={() => void auth.getAccessToken().catch((reason: Error) => setError(reason.message))}
          >
            Get token
          </button>
        </>
      ) : null}
      {error ? <p>{error}</p> : null}
    </>
  )
}

describe('AuthProvider redirect flow', () => {
  afterEach(cleanup)

  beforeEach(async () => {
    vi.resetModules()
    vi.clearAllMocks()
    vi.stubEnv('VITE_ENTRA_TENANT_ID', 'tenant-id')
    vi.stubEnv('VITE_ENTRA_CLIENT_ID', 'client-id')
    vi.stubEnv('VITE_API_SCOPE', 'api://client-id/BankServicing.Access')
    mocks.initialize.mockResolvedValue(undefined)
    mocks.handleRedirectPromise.mockResolvedValue(null)
    mocks.getAllAccounts.mockReturnValue([])
    mocks.loginRedirect.mockResolvedValue(undefined)
    mocks.logoutRedirect.mockResolvedValue(undefined)
    mocks.acquireTokenPopup.mockResolvedValue({ accessToken: 'refreshed-token' })

    ;({ AuthProvider } = await import('./AuthProvider'))
    ;({ useAuth } = await import('./authContext'))
  })

  it('uses a same-window redirect for sign-in', async () => {
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }))

    expect(mocks.loginRedirect).toHaveBeenCalledWith({
      scopes: ['api://client-id/BankServicing.Access'],
    })
    expect(mocks.configuration).toMatchObject({
      cache: {
        cacheLocation: 'sessionStorage',
      },
    })
  })

  it('processes the redirect only once when Strict Mode remounts effects', async () => {
    const account = { homeAccountId: 'home-id', username: 'presenter@example.com' }
    mocks.handleRedirectPromise.mockResolvedValue({ account })

    render(
      <StrictMode>
        <AuthProvider>
          <Consumer />
        </AuthProvider>
      </StrictMode>,
    )

    expect(await screen.findByRole('button', { name: 'Get token' })).toBeInTheDocument()
    expect(mocks.initialize).toHaveBeenCalledTimes(1)
    expect(mocks.handleRedirectPromise).toHaveBeenCalledTimes(1)
    expect(mocks.setActiveAccount).toHaveBeenCalledOnce()
    expect(mocks.setActiveAccount).toHaveBeenCalledWith(account)
  })

  it('recovers from a stale redirect response whose request cache was already consumed', async () => {
    window.history.pushState(null, '', '/#code=stale')
    mocks.handleRedirectPromise.mockRejectedValue(
      new mocks.MockBrowserAuthError('no_token_request_cache_error'),
    )

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    )

    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(window.location.hash).toBe('')
    expect(mocks.setActiveAccount).toHaveBeenCalledWith(null)
  })

  it('uses a popup for interactive token renewal without leaving the chat', async () => {
    const account = { homeAccountId: 'home-id', username: 'presenter@example.com' }
    mocks.handleRedirectPromise.mockResolvedValue({ account })
    mocks.acquireTokenSilent.mockRejectedValue(new mocks.MockInteractionRequiredAuthError())

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Get token' }))
    await waitFor(() => expect(mocks.acquireTokenPopup).toHaveBeenCalledWith({
      scopes: ['api://client-id/BankServicing.Access'],
      account,
      loginHint: 'presenter@example.com',
    }))
    expect(mocks.acquireTokenSilent).toHaveBeenCalledWith({
      scopes: ['api://client-id/BankServicing.Access'],
      account,
      loginHint: 'presenter@example.com',
      cacheLookupPolicy: 'access-token-and-refresh-token',
    })

    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(mocks.logoutRedirect).toHaveBeenCalledWith({
      account,
      postLogoutRedirectUri: window.location.origin,
    })
  })

  it('recovers from the observed MSAL timeout with an interactive token request', async () => {
    const account = { homeAccountId: 'home-id', username: 'presenter@example.com' }
    mocks.handleRedirectPromise.mockResolvedValue({ account })
    mocks.acquireTokenSilent.mockRejectedValue(new mocks.MockBrowserAuthError('timed_out'))

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Get token' }))

    await waitFor(() => expect(mocks.acquireTokenPopup).toHaveBeenCalledTimes(1))
  })
})
