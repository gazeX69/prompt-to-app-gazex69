import os
import json
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.resolve()
VITE_TS = TEMPLATES_DIR / "vite-react-ts"

os.makedirs(VITE_TS / "src", exist_ok=True)

# package.json
package_json = {
  "name": "vite-react-ts-template",
  "private": True,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "lucide-react": "^0.263.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.14",
    "postcss": "^8.4.27",
    "tailwindcss": "^3.3.3",
    "typescript": "^5.5.3",
    "vite": "^5.4.1"
  }
}
with open(VITE_TS / "package.json", "w") as f:
    json.dump(package_json, f, indent=2)

# vite.config.ts
with open(VITE_TS / "vite.config.ts", "w") as f:
    f.write('''import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
''')

# tailwind.config.js
with open(VITE_TS / "tailwind.config.js", "w") as f:
    f.write('''/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
''')

# postcss.config.js
with open(VITE_TS / "postcss.config.js", "w") as f:
    f.write('''export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
''')

# tsconfig.json
with open(VITE_TS / "tsconfig.json", "w") as f:
    f.write('''{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
''')

# tsconfig.node.json
with open(VITE_TS / "tsconfig.node.json", "w") as f:
    f.write('''{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
''')

# index.html
with open(VITE_TS / "index.html", "w") as f:
    f.write('''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AI Application</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
''')

# src/index.css
with open(VITE_TS / "src" / "index.css", "w") as f:
    f.write('''@tailwind base;
@tailwind components;
@tailwind utilities;

body {
    background-color: #f3f4f6;
    font-family: system-ui, -apple-system, sans-serif;
}
''')

# src/main.tsx
with open(VITE_TS / "src" / "main.tsx", "w") as f:
    f.write('''import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
''')

# src/App.tsx
with open(VITE_TS / "src" / "App.tsx", "w") as f:
    f.write('''import React from 'react'

export default function App() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <h1 className="text-3xl font-bold text-blue-600">Application Scaffolding...</h1>
    </div>
  )
}
''')

print("Template vite-react-ts generated successfully.")
