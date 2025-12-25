import { FileText, Upload, Edit, Download, CheckCircle, Zap } from 'lucide-react';
import { useRouter } from '../context/RouterContext';
import { useAuth } from '../context/AuthContext';

export const Home = () => {
  const { navigate } = useRouter();
  const { isAuthenticated } = useAuth();

  const features = [
    {
      icon: Upload,
      title: 'Upload Forms',
      description: 'Upload your forms in PDF or image format easily',
    },
    {
      icon: Zap,
      title: 'AI Processing',
      description: 'Our AI automatically fills your forms intelligently',
    },
    {
      icon: Edit,
      title: 'Edit & Review',
      description: 'Review and make changes to your filled forms',
    },
    {
      icon: Download,
      title: 'Download',
      description: 'Get your completed forms in the format you need',
    },
  ];

  return (
    <div className="min-h-[calc(100vh-4rem)]">
      <section className="bg-gradient-to-br from-primary-cream via-white to-primary-pink/20 py-20 px-4">
        <div className="max-w-7xl mx-auto text-center">
          <div className="flex justify-center mb-6">
            <FileText className="w-20 h-20 text-primary-olive" />
          </div>
          <h1 className="text-5xl md:text-6xl font-bold text-primary-olive mb-6">
            AsaanForm
          </h1>
          <p className="text-xl md:text-2xl text-gray-700 mb-8 max-w-3xl mx-auto">
            Your AI-powered form filling assistant. Upload, process, and download
            your forms with ease.
          </p>
          <button
            onClick={() => navigate(isAuthenticated ? 'upload-form' : 'login')}
            className="px-8 py-4 bg-primary-blue text-white text-lg font-semibold rounded-xl hover:opacity-90 transition-all transform hover:scale-105 shadow-lg"
          >
            Get Started
          </button>
        </div>
      </section>

      <section className="py-20 px-4 bg-white">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-4xl font-bold text-center text-primary-olive mb-16">
            How It Works
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => (
              <div
                key={index}
                className="bg-primary-cream p-8 rounded-2xl shadow-md hover:shadow-xl transition-shadow"
              >
                <div className="w-14 h-14 bg-primary-blue/10 rounded-full flex items-center justify-center mb-6">
                  <feature.icon className="w-7 h-7 text-primary-blue" />
                </div>
                <h3 className="text-xl font-semibold text-primary-olive mb-3">
                  {feature.title}
                </h3>
                <p className="text-gray-600">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-20 px-4 bg-primary-gray/20">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-4xl font-bold text-center text-primary-olive mb-16">
            Why Choose AsaanForm?
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                title: 'Fast & Accurate',
                description:
                  'Our AI ensures quick processing with high accuracy',
              },
              {
                title: 'Secure',
                description: 'Your data is encrypted and securely stored',
              },
              {
                title: 'Easy to Use',
                description: 'Simple interface designed for everyone',
              },
            ].map((benefit, index) => (
              <div
                key={index}
                className="bg-white p-8 rounded-2xl shadow-md text-center"
              >
                <CheckCircle className="w-12 h-12 text-primary-blue mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-primary-olive mb-3">
                  {benefit.title}
                </h3>
                <p className="text-gray-600">{benefit.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};