import { Component, type ErrorInfo, type ReactNode } from "react";
import { useLocation } from "react-router-dom";

interface Props {
  children: ReactNode;
  fallback: (error: { message?: string }, reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Route error boundary caught:", error, info);
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return this.props.fallback(this.state.error, this.reset);
    }
    return this.props.children;
  }
}

/**
 * A route-scoped boundary.
 *
 * A caught error is state about one screen, so it is thrown away when the
 * screen changes. Keying on the pathname remounts the boundary on navigation,
 * which is what lets someone who hits a broken page leave it by clicking a nav
 * link. Without the key the fallback stayed pinned over every later route and
 * the only way out was a reload.
 */
export function RoutedErrorBoundary({
  children,
  fallback,
}: {
  children: ReactNode;
  fallback: Props["fallback"];
}) {
  const location = useLocation();
  return (
    <ErrorBoundary key={location.pathname} fallback={fallback}>
      {children}
    </ErrorBoundary>
  );
}
