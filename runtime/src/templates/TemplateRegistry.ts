import fs from 'fs/promises';
import path from 'path';
import { eventBus } from '../events/RuntimeEventBus.js';
import { RuntimeEventType } from '../types/events.js';

export class TemplateRegistry {
  public async scaffold(templateId: string, targetDir: string): Promise<void> {
    if (templateId === 'vite-react-ts') {
      await this.scaffoldViteReactTs(targetDir);
      eventBus.emitEvent(RuntimeEventType.TEMPLATE_CREATED, { templateId, targetDir });
    } else {
      throw new Error(`Template ${templateId} not found`);
    }
  }

  private async scaffoldViteReactTs(targetDir: string) {
    const files = {
      'package.json': JSON.stringify({
        name: "runtime-workspace",
        private: true,
        version: "0.0.0",
        type: "module",
        scripts: {
          "dev": "vite",
          "build": "tsc -b && vite build",
          "preview": "vite preview"
        },
        dependencies: {
          "react": "^18.3.1",
          "react-dom": "^18.3.1"
        },
        devDependencies: {
          "@types/react": "^18.3.3",
          "@types/react-dom": "^18.3.0",
          "@vitejs/plugin-react": "^4.3.1",
          "typescript": "^5.5.3",
          "vite": "^5.4.1"
        }
      }, null, 2),
      'vite.config.ts': `import { defineConfig } from 'vite'\nimport react from '@vitejs/plugin-react'\n\nexport default defineConfig({\n  plugins: [react()],\n  server: { host: '0.0.0.0', port: 3000, strictPort: false }\n})\n`,
      'tsconfig.json': `{\n  "compilerOptions": {\n    "target": "ES2020",\n    "useDefineForClassFields": true,\n    "lib": ["ES2020", "DOM", "DOM.Iterable"],\n    "module": "ESNext",\n    "skipLibCheck": true,\n    "moduleResolution": "bundler",\n    "allowImportingTsExtensions": true,\n    "resolveJsonModule": true,\n    "isolatedModules": true,\n    "noEmit": true,\n    "jsx": "react-jsx",\n    "strict": true,\n    "noUnusedLocals": true,\n    "noUnusedParameters": true,\n    "noFallthroughCasesInSwitch": true\n  },\n  "include": ["src"]\n}\n`,
      'index.html': `<!doctype html>\n<html lang="en">\n  <head>\n    <meta charset="UTF-8" />\n    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n    <title>Vite + React + TS</title>\n  </head>\n  <body>\n    <div id="root"></div>\n    <script type="module" src="/src/main.tsx"></script>\n  </body>\n</html>\n`,
      'src/main.tsx': `import React from 'react'\nimport ReactDOM from 'react-dom/client'\nimport App from './App.tsx'\n\nReactDOM.createRoot(document.getElementById('root')!).render(\n  <React.StrictMode>\n    <App />\n  </React.StrictMode>,\n)\n`,
      'src/App.tsx': `import React from 'react';\n\nfunction App() {\n  return (\n    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>\n      <h1>Welcome to Runtime Core</h1>\n      <p>This is a strictly generated Vite React TS template.</p>\n    </div>\n  );\n}\n\nexport default App;\n`,
    };

    await fs.mkdir(path.join(targetDir, 'src'), { recursive: true });

    for (const [filepath, content] of Object.entries(files)) {
      await fs.writeFile(path.join(targetDir, filepath), content);
    }
  }
}

export const templateRegistry = new TemplateRegistry();
