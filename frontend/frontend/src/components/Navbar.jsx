import { FileText, User, LogOut } from 'lucide-react';
import { useRouter } from '../context/RouterContext';
import { useAuth } from '../context/AuthContext';

export const Navbar = () => {
  const { navigate, currentRoute } = useRouter();
  const { isAuthenticated, user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('home');
  };

  return (
    <nav className="bg-primary-cream shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div
            className="flex items-center gap-2 cursor-pointer"
            onClick={() => navigate('home')}
          >
            <FileText className="w-8 h-8 text-primary-olive" />
            <span className="text-2xl font-bold text-primary-olive">
              AsaanForm
            </span>
          </div>

          <div className="flex items-center gap-6">
            <button
              onClick={() => navigate('home')}
              className={`text-sm font-medium transition-colors ${
                currentRoute === 'home'
                  ? 'text-primary-olive'
                  : 'text-gray-600 hover:text-primary-olive'
              }`}
            >
              Home
            </button>
            <button
              onClick={() => navigate('about')}
              className={`text-sm font-medium transition-colors ${
                currentRoute === 'about'
                  ? 'text-primary-olive'
                  : 'text-gray-600 hover:text-primary-olive'
              }`}
            >
              About
            </button>

            {isAuthenticated ? (
              <>
                <button
                  onClick={() => navigate('profile')}
                  className="flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-primary-olive transition-colors"
                >
                  <User className="w-4 h-4" />
                  {user?.name}
                </button>
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-2 px-4 py-2 bg-primary-pink text-white rounded-lg hover:opacity-90 transition-opacity"
                >
                  <LogOut className="w-4 h-4" />
                  Logout
                </button>
              </>
            ) : (
              <button
                onClick={() => navigate('login')}
                className="px-4 py-2 bg-primary-blue text-white rounded-lg hover:opacity-90 transition-opacity"
              >
                Login
              </button>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};