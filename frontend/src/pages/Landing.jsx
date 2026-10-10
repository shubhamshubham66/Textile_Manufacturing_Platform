import Navbar from "../components/Navbar.jsx";
import Hero from "../components/Hero.jsx";
import About from "../components/About.jsx";
import HowItWorks from "../components/HowItWorks.jsx";
import Features from "../components/Features.jsx";
import AiSection from "../components/AiSection.jsx";
import CtaStrip from "../components/CtaStrip.jsx";
import Footer from "../components/Footer.jsx";
import ChatBubble from "../components/ChatBubble.jsx";
import "../landing.css";

// Public landing page. Composes the navbar, all sections and the footer, plus the
// floating chat-bubble mount point (built later by the mini developer).
export default function Landing() {
  return (
    <div className="lp">
      <Navbar />
      <main>
        <Hero />
        <About />
        <HowItWorks />
        <Features />
        <AiSection />
        <CtaStrip />
      </main>
      <Footer />
      <ChatBubble />
    </div>
  );
}
