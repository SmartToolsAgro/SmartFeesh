import { i18n } from "@frutti/i18n";
import { Button, Card } from "@frutti/ui";
import { Component, type ReactNode } from "react";

// A screen that crashes shows a message and a way out instead of a blank white page; the tabs stay usable.
export class ScreenError extends Component<{ children: ReactNode; resetKey: string }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error(error);
  }

  componentDidUpdate(previous: { resetKey: string }) {
    // Moving to another tab gives the screen a fresh try.
    if (this.state.failed && previous.resetKey !== this.props.resetKey) this.setState({ failed: false });
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <Card className="space-y-3" role="alert">
        <p className="text-lg font-semibold">{i18n.t("truck.crash.title")}</p>
        <p className="text-ink-2">{i18n.t("truck.crash.body")}</p>
        <Button size="lg" onClick={() => window.location.reload()}>
          {i18n.t("truck.crash.reload")}
        </Button>
      </Card>
    );
  }
}
