import ReactDOM from "react-dom/client";
import "../../scrollcraft/builds/panda-landing/scrollcraft.js";
import "../../scrollcraft/builds/panda-landing/scrollcraft.css";
import "./styles/landing.css";
import Landing from "./pages/Landing";

// Keep previously shared dashboard hash URLs working after introducing the landing page.
if (
  /^#\/(?:$|\?|risk(?:$|\?)|research(?:$|\?)|what-if(?:$|\?))/.test(
    location.hash,
  )
) {
  const destination = new URL("app.html", location.href);
  destination.hash = location.hash;
  location.replace(destination.href);
} else {
  ReactDOM.createRoot(document.getElementById("root")!).render(<Landing />);
}
