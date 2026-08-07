import { createContext, useContext } from 'react'
import type { AccountInfo } from '@azure/msal-browser'

export interface AuthValue {
  account: AccountInfo | null
  initializing: boolean
  configurationError: string | null
  isReviewer: boolean
  isAdmin: boolean
  signIn: () => Promise<void>
  signOut: () => Promise<void>
  getAccessToken: () => Promise<string>
}

export const AuthContext = createContext<AuthValue | null>(null)

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return value
}
