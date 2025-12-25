import { useState } from 'react';
import { Eye, Save, Download } from 'lucide-react';
import { useRouter } from '../context/RouterContext';

export const EditForm = () => {
  const [formData, setFormData] = useState({
    fullName: 'John Doe',
    email: 'john.doe@example.com',
    phone: '+1 (555) 123-4567',
    address: '123 Main Street, City, State 12345',
    dateOfBirth: '1990-01-15',
    occupation: 'Software Engineer',
    experience: '5 years',
    education: 'Bachelor of Science in Computer Science',
  });

  const [isPreview, setIsPreview] = useState(false);
  const { navigate } = useRouter();

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSave = () => {
    alert('Form saved successfully!');
  };

  const handleDownload = () => {
    navigate('download');
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] py-12 px-4">
      <div className="max-w-5xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-primary-olive mb-2">
              {isPreview ? 'Preview Form' : 'Edit Filled Form'}
            </h1>
            <p className="text-lg text-gray-600">
              {isPreview
                ? 'Review your completed form'
                : 'Review and modify the AI-filled information'}
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => setIsPreview(!isPreview)}
              className="flex items-center gap-2 px-4 py-2 bg-primary-gray text-primary-olive rounded-lg hover:opacity-90 transition-opacity"
            >
              <Eye className="w-5 h-5" />
              {isPreview ? 'Edit' : 'Preview'}
            </button>
            {!isPreview && (
              <button
                onClick={handleSave}
                className="flex items-center gap-2 px-4 py-2 bg-primary-blue text-white rounded-lg hover:opacity-90 transition-opacity"
              >
                <Save className="w-5 h-5" />
                Save
              </button>
            )}
          </div>
        </div>

        <div className="bg-white rounded-2xl p-8 shadow-lg">
          {isPreview ? (
            <div className="space-y-6">
              <div className="border-b border-primary-gray pb-4">
                <h2 className="text-2xl font-bold text-primary-olive mb-6">
                  Application Form
                </h2>
              </div>
              {Object.entries(formData).map(([key, value]) => (
                <div key={key} className="flex border-b border-primary-gray/30 pb-4">
                  <div className="w-1/3">
                    <p className="font-semibold text-primary-olive capitalize">
                      {key.replace(/([A-Z])/g, ' $1').trim()}:
                    </p>
                  </div>
                  <div className="w-2/3">
                    <p className="text-gray-700">{value}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-6">
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-primary-olive mb-2">
                    Full Name
                  </label>
                  <input
                    type="text"
                    name="fullName"
                    value={formData.fullName}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-primary-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-blue"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-primary-olive mb-2">
                    Email
                  </label>
                  <input
                    type="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-primary-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-blue"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-primary-olive mb-2">
                    Phone
                  </label>
                  <input
                    type="tel"
                    name="phone"
                    value={formData.phone}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-primary-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-blue"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-primary-olive mb-2">
                    Date of Birth
                  </label>
                  <input
                    type="date"
                    name="dateOfBirth"
                    value={formData.dateOfBirth}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-primary-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-blue"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-primary-olive mb-2">
                  Address
                </label>
                <textarea
                  name="address"
                  value={formData.address}
                  onChange={handleChange}
                  rows={3}
                  className="w-full px-4 py-3 border border-primary-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-blue"
                />
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-primary-olive mb-2">
                    Occupation
                  </label>
                  <input
                    type="text"
                    name="occupation"
                    value={formData.occupation}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-primary-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-blue"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-primary-olive mb-2">
                    Experience
                  </label>
                  <input
                    type="text"
                    name="experience"
                    value={formData.experience}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-primary-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-blue"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-primary-olive mb-2">
                  Education
                </label>
                <input
                  type="text"
                  name="education"
                  value={formData.education}
                  onChange={handleChange}
                  className="w-full px-4 py-3 border border-primary-gray rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-blue"
                />
              </div>
            </div>
          )}

          <div className="mt-8 pt-6 border-t border-primary-gray">
            <button
              onClick={handleDownload}
              className="w-full flex items-center justify-center gap-2 py-3 bg-primary-pink text-white rounded-lg font-semibold hover:opacity-90 transition-opacity"
            >
              <Download className="w-5 h-5" />
              Continue to Download
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};