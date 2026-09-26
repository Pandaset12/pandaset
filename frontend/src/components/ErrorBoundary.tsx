import { Component } from "react";
import type { ReactNode, ErrorInfo } from "react";
import { ArrowPath as RotateCcw } from "./icons";

export class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: boolean }
> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("PandaSet rendering error", error, info.componentStack);
  }
  render() {
    return this.state.error ? (
      <main className="error-page">
        <h1>Something didn’t load.</h1>
        <p>Your sample portfolio can be restored by reloading the page.</p>
        <button className="button dark" onClick={() => location.reload()}>
          Reload PandaSet
          <RotateCcw size={16} />
        </button>
      </main>
    ) : (
      this.props.children
    );
  }
}
