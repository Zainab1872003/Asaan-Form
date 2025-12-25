import { Navbar } from './Navbar';
import { Chatbot } from './Chatbot';

export const Layout = ({ children }) => {
  return (
    <div className="min-h-screen bg-primary-cream">
      <Navbar />
      <main className="min-h-[calc(100vh-4rem)]">{children}</main>
      <Chatbot />
    </div>
  );
};