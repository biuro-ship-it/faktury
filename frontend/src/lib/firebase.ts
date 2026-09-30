import { initializeApp } from 'firebase/app'
import { type Auth, GoogleAuthProvider, getAuth } from 'firebase/auth'

const konfiguracja = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

/** Bez konfiguracji ekran logowania pokazuje komunikat zamiast wywracać aplikację. */
export const firebaseSkonfigurowany = Object.values(konfiguracja).every(Boolean)

export const auth: Auth | null = firebaseSkonfigurowany ? getAuth(initializeApp(konfiguracja)) : null

export const dostawcaGoogle = new GoogleAuthProvider()
// Zawsze pytaj o konto — przy dwóch kontach Google łatwo wejść nie tym.
dostawcaGoogle.setCustomParameters({ prompt: 'select_account' })
