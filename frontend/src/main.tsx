import { createRoot } from 'react-dom/client'
import '@fontsource-variable/bricolage-grotesque'
import '@fontsource-variable/figtree'
import './design/tokens.css'
import './restaurant.css'
import { App } from './components/App'
createRoot(document.getElementById('root')!).render(<App/> )
