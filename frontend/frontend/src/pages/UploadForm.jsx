import { useState } from 'react';
import { Upload, FileText, Image, CheckCircle } from 'lucide-react';
import { useRouter } from '../context/RouterContext';

export const UploadForm = () => {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const { navigate } = useRouter();

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    setSelectedFiles([...selectedFiles, ...files]);
  };

  const handleFileSelect = (e) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      setSelectedFiles([...selectedFiles, ...files]);
    }
  };

  const handleContinue = () => {
    navigate('upload-documents');
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] py-12 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-primary-olive mb-4">
            Upload Your Forms
          </h1>
          <p className="text-lg text-gray-600">
            Upload the forms you want to fill in PDF or image format
          </p>
        </div>

        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-3 border-dashed rounded-2xl p-12 text-center transition-all ${
            isDragging
              ? 'border-primary-blue bg-primary-blue/5'
              : 'border-primary-gray bg-white'
          }`}
        >
          <Upload
            className={`w-20 h-20 mx-auto mb-6 ${
              isDragging ? 'text-primary-blue' : 'text-primary-olive'
            }`}
          />
          <h3 className="text-2xl font-semibold text-primary-olive mb-2">
            Drag and drop your forms here
          </h3>
          <p className="text-gray-600 mb-6">or click to browse files</p>

          <input
            type="file"
            multiple
            accept=".pdf,image/*"
            onChange={handleFileSelect}
            className="hidden"
            id="file-upload"
          />
          <label
            htmlFor="file-upload"
            className="inline-block px-6 py-3 bg-primary-blue text-white rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
          >
            Browse Files
          </label>

          <p className="text-sm text-gray-500 mt-4">
            Supported formats: PDF, JPG, PNG
          </p>
        </div>

        {selectedFiles.length > 0 && (
          <div className="mt-8 bg-white rounded-2xl p-6 shadow-lg">
            <h3 className="text-xl font-semibold text-primary-olive mb-4">
              Selected Files ({selectedFiles.length})
            </h3>
            <div className="space-y-3">
              {selectedFiles.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-4 bg-primary-cream rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    {file.type.includes('pdf') ? (
                      <FileText className="w-6 h-6 text-primary-blue" />
                    ) : (
                      <Image className="w-6 h-6 text-primary-pink" />
                    )}
                    <div>
                      <p className="font-medium text-primary-olive">
                        {file.name}
                      </p>
                      <p className="text-sm text-gray-600">
                        {(file.size / 1024).toFixed(2)} KB
                      </p>
                    </div>
                  </div>
                  <CheckCircle className="w-5 h-5 text-green-500" />
                </div>
              ))}
            </div>

            <button
              onClick={handleContinue}
              className="mt-6 w-full py-3 bg-primary-blue text-white rounded-lg font-semibold hover:opacity-90 transition-opacity"
            >
              Continue to Upload Documents
            </button>
          </div>
        )}
      </div>
    </div>
  );
};