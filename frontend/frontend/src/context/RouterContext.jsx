import { createContext, useContext, useState, useEffect } from 'react';

const RouterContext = createContext(undefined);

export const RouterProvider = ({ children }) => {
  const [currentRoute, setCurrentRoute] = useState(() => {
    const hash = window.location.hash.slice(1);
    return hash || 'home';
  });

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.slice(1);
      setCurrentRoute(hash || 'home');
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigate = (route) => {
    window.location.hash = route;
    setCurrentRoute(route);
  };

  return (
    <RouterContext.Provider value={{ currentRoute, navigate }}>
      {children}
    </RouterContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useRouter = () => {
  const context = useContext(RouterContext);
  if (!context) {
    throw new Error('useRouter must be used within RouterProvider');
  }
  return context;
};