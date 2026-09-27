import ReactDOM from "react-dom/client";
import "../../scrollcraft/builds/panda-landing/scrollcraft.js";
import "../../scrollcraft/builds/panda-landing/scrollcraft.css";
import "./styles/landing.css";
import Landing from "./pages/Landing";
import { landingRedirect } from "./lib/landingRedirect";

const destination = landingRedirect(location.href);
if (destination) {
  location.replace(destination);
} else {
  ReactDOM.createRoot(document.getElementById("root")!).render(<Landing />);
}
