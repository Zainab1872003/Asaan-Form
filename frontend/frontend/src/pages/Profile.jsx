import { FileText, CheckCircle, Clock, XCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useRouter } from '../context/RouterContext';

export const Profile = () => {
  const { user } = useAuth();
  const { navigate } = useRouter();

  const forms = [
    {
      id: 1,
      name: 'Job Application Form',
      status: 'completed',
      date: '2024-01-15',
      documents: 3,
    },
    {
      id: 2,
      name: 'Visa Application',
      status: 'processing',
      date: '2024-01-14',
      documents: 5,
    },
    {
      id: 3,
      name: 'Insurance Form',
      status: 'completed',
      date: '2024-01-10',
      documents: 2,
    },
    {
      id: 4,
      name: 'Loan Application',
      status: 'failed',
      date: '2024-01-08',
      documents: 4,
    },
  ];

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'processing':
        return <Clock className="w-5 h-5 text-primary-blue" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />;
      default:
        return null;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'processing':
        return 'bg-blue-100 text-primary-blue';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] py-12 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="bg-white rounded-2xl p-8 shadow-lg mb-8">
          <div className="flex items-center gap-6">
            <div className="w-24 h-24 bg-primary-blue rounded-full flex items-center justify-center text-white text-3xl font-bold">
              {user?.name?.charAt(0)?.toUpperCase()}
            </div>
            <div>
              <h1 className="text-3xl font-bold text-primary-olive mb-2">
                {user?.name}
              </h1>
              <p className="text-gray-600">{user?.email}</p>
              <div className="flex gap-4 mt-4">
                <div className="text-center">
                  <p className="text-2xl font-bold text-primary-blue">
                    {forms.length}
                  </p>
                  <p className="text-sm text-gray-600">Total Forms</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-green-500">
                    {forms.filter((f) => f.status === 'completed').length}
                  </p>
                  <p className="text-sm text-gray-600">Completed</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-primary-blue">
                    {forms.filter((f) => f.status === 'processing').length}
                  </p>
                  <p className="text-sm text-gray-600">Processing</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-8 shadow-lg">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-primary-olive">
              Your Forms
            </h2>
            <button
              onClick={() => navigate('upload-form')}
              className="px-6 py-2 bg-primary-blue text-white rounded-lg hover:opacity-90 transition-opacity"
            >
              New Form
            </button>
          </div>

          <div className="space-y-4">
            {forms.map((form) => (
              <div
                key={form.id}
                className="flex items-center justify-between p-6 bg-primary-cream rounded-xl hover:shadow-md transition-shadow cursor-pointer"
                onClick={() =>
                  form.status === 'completed' && navigate('download')
                }
              >
                <div className="flex items-center gap-4">
                  <FileText className="w-8 h-8 text-primary-olive" />
                  <div>
                    <h3 className="font-semibold text-primary-olive text-lg">
                      {form.name}
                    </h3>
                    <p className="text-sm text-gray-600">
                      {form.documents} documents • {form.date}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`px-4 py-2 rounded-full text-sm font-medium flex items-center gap-2 ${getStatusColor(
                      form.status
                    )}`}
                  >
                    {getStatusIcon(form.status)}
                    {form.status.charAt(0).toUpperCase() + form.status.slice(1)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};