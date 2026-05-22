import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface Props {
  children?: ReactNode;
  fallbackName?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`ErrorBoundary caught error in ${this.props.fallbackName || 'component'}:`, error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full w-full p-4 bg-background border border-red-500/20 rounded-xl">
          <AlertTriangle className="w-8 h-8 text-red-500 mb-4 opacity-80" />
          <h2 className="text-[13px] font-semibold text-gray-200 mb-1">
            {this.props.fallbackName || 'Component'} Failed
          </h2>
          <p className="text-[11px] text-gray-500 font-mono bg-black/40 px-3 py-2 rounded break-all max-w-full text-center">
            {this.state.error?.message || 'Unknown runtime error'}
          </p>
          <button 
            className="mt-4 bg-accent hover:bg-accent/80 text-[12px] font-medium px-3 py-1.5 rounded transition-colors"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Retry Render
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
