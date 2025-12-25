import { RouterProvider, useRouter } from './context/RouterContext';
import { AuthProvider } from './context/AuthContext';
import { Layout } from './components/Layout';
import { Home } from './pages/Home';
import { About } from './pages/About';
import { Login } from './pages/Login';
import { Signup } from './pages/Signup';
import { UploadForm } from './pages/UploadForm';
import { UploadDocuments } from './pages/UploadDocuments';
import { EditForm } from './pages/EditForm';
import { Profile } from './pages/Profile';
import { Download } from './pages/Download';

function AppContent() {
  const { currentRoute } = useRouter();

  const renderPage = () => {
    switch (currentRoute) {
      case 'home':
        return <Home />;
      case 'about':
        return <About />;
      case 'login':
        return <Login />;
      case 'signup':
        return <Signup />;
      case 'upload-form':
        return <UploadForm />;
      case 'upload-documents':
        return <UploadDocuments />;
      case 'edit-form':
        return <EditForm />;
      case 'profile':
        return <Profile />;
      case 'download':
        return <Download />;
      default:
        return <Home />;
    }
  };

  return (
    <Layout>
      {renderPage()}
    </Layout>
  );
}

function App() {
  return (
    <AuthProvider>
      <RouterProvider>
        <AppContent />
      </RouterProvider>
    </AuthProvider>
  );
}

export default App;