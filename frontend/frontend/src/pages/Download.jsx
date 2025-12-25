import { useState } from 'react';
import { Download as DownloadIcon, FileText, Image, CheckCircle } from 'lucide-react';
import { useRouter } from '../context/RouterContext';

export const Download = () => {
  const [selectedFormat, setSelectedFormat] = useState('pdf');
  const [compressionLevel, setCompressionLevel] = useState('medium');
  const { navigate } = useRouter();

  const handleDownload = () => {
    alert(`Downloading filled form as ${selectedFormat.toUpperCase()} with ${compressionLevel} compression`);
  };

  const documents = [
    { name: 'ID Proof.pdf', size: '2.3 MB', type: 'pdf' },
    { name: 'Certificate.jpg', size: '1.8 MB', type: 'image' },
    { name: 'Resume.pdf', size: '456 KB', type: 'pdf' },
  ];

  return (
    <div className="min-h-[calc(100vh-4rem)] py-12 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-12 h-12 text-green-500" />
          </div>
          <h1 className="text-4xl font-bold text-primary-olive mb-4">
            Form Processing Complete!
          </h1>
          <p className="text-lg text-gray-600">
            Your form has been filled successfully. Download it below.
          </p>
        </div>

        <div className="bg-white rounded-2xl p-8 shadow-lg mb-6">
          <h2 className="text-2xl font-semibold text-primary-olive mb-6">
            Download Filled Form
          </h2>

          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-primary-olive mb-3">
                Select Format
              </label>
              <div className="grid grid-cols-3 gap-4">
                {['pdf', 'docx', 'image'].map((format) => (
                  <button
                    key={format}
                    onClick={() => setSelectedFormat(format)}
                    className={`p-4 border-2 rounded-lg transition-all ${
                      selectedFormat === format
                        ? 'border-primary-blue bg-primary-blue/5'
                        : 'border-primary-gray hover:border-primary-blue/50'
                    }`}
                  >
                    <p className="font-medium text-primary-olive uppercase">
                      {format}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-primary-olive mb-3">
                Compression Level
              </label>
              <div className="grid grid-cols-3 gap-4">
                {[
                  { value: 'low', label: 'Low', desc: 'Best quality' },
                  { value: 'medium', label: 'Medium', desc: 'Balanced' },
                  { value: 'high', label: 'High', desc: 'Smallest size' },
                ].map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setCompressionLevel(option.value)}
                    className={`p-4 border-2 rounded-lg transition-all ${
                      compressionLevel === option.value
                        ? 'border-primary-blue bg-primary-blue/5'
                        : 'border-primary-gray hover:border-primary-blue/50'
                    }`}
                  >
                    <p className="font-medium text-primary-olive">
                      {option.label}
                    </p>
                    <p className="text-xs text-gray-600 mt-1">{option.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={handleDownload}
              className="w-full flex items-center justify-center gap-2 py-4 bg-primary-blue text-white rounded-lg font-semibold hover:opacity-90 transition-opacity text-lg"
            >
              <DownloadIcon className="w-6 h-6" />
              Download Filled Form
            </button>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-8 shadow-lg">
          <h2 className="text-2xl font-semibold text-primary-olive mb-6">
            Download Your Documents
          </h2>
          <p className="text-gray-600 mb-6">
            Download compressed versions of your uploaded documents
          </p>

          <div className="space-y-3">
            {documents.map((doc, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-4 bg-primary-cream rounded-lg hover:shadow-md transition-shadow"
              >
                <div className="flex items-center gap-3">
                  {doc.type === 'pdf' ? (
                    <FileText className="w-6 h-6 text-primary-blue" />
                  ) : (
                    <Image className="w-6 h-6 text-primary-pink" />
                  )}
                  <div>
                    <p className="font-medium text-primary-olive">{doc.name}</p>
                    <p className="text-sm text-gray-600">
                      Original: {doc.size}
                    </p>
                  </div>
                </div>
                <button className="px-4 py-2 bg-primary-blue text-white rounded-lg hover:opacity-90 transition-opacity">
                  Download
                </button>
              </div>
            ))}
          </div>

          <button
            onClick={() => navigate('profile')}
            className="w-full mt-6 py-3 border-2 border-primary-olive text-primary-olive rounded-lg font-semibold hover:bg-primary-olive hover:text-white transition-all"
          >
            Back to Profile
          </button>
        </div>
      </div>
    </div>
  );
};