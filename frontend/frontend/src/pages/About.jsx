import { Target, Users, Award, Heart } from 'lucide-react';

export const About = () => {
  return (
    <div className="min-h-[calc(100vh-4rem)] py-16 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-primary-olive mb-6">
            About AsaanForm
          </h1>
          <p className="text-xl text-gray-700 max-w-3xl mx-auto leading-relaxed">
            AsaanForm is revolutionizing the way people handle form filling. We
            leverage cutting-edge AI technology to make document processing
            effortless, accurate, and fast.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-12 mb-16">
          <div className="bg-white p-8 rounded-2xl shadow-lg">
            <Target className="w-12 h-12 text-primary-blue mb-4" />
            <h2 className="text-2xl font-bold text-primary-olive mb-4">
              Our Mission
            </h2>
            <p className="text-gray-700 leading-relaxed">
              To simplify form filling and document management for everyone. We
              believe that administrative tasks shouldn't consume your valuable
              time. Our AI-powered solution ensures accuracy while saving you
              hours of manual work.
            </p>
          </div>

          <div className="bg-white p-8 rounded-2xl shadow-lg">
            <Award className="w-12 h-12 text-primary-pink mb-4" />
            <h2 className="text-2xl font-bold text-primary-olive mb-4">
              Our Vision
            </h2>
            <p className="text-gray-700 leading-relaxed">
              To become the world's most trusted AI form filling platform,
              helping millions of users streamline their document workflows and
              focus on what truly matters in their personal and professional
              lives.
            </p>
          </div>
        </div>

        <div className="bg-gradient-to-br from-primary-cream to-primary-pink/20 p-12 rounded-3xl mb-16">
          <h2 className="text-3xl font-bold text-primary-olive mb-8 text-center">
            What We Offer
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                title: 'AI-Powered Processing',
                description:
                  'Advanced machine learning algorithms that understand and fill forms intelligently',
              },
              {
                title: 'Multi-Format Support',
                description:
                  'Works with PDFs, images, and various document formats seamlessly',
              },
              {
                title: 'Secure Storage',
                description:
                  'Enterprise-grade security ensures your sensitive information stays protected',
              },
              {
                title: 'Easy Editing',
                description:
                  'Review and modify AI-filled forms before finalizing',
              },
              {
                title: 'Quick Download',
                description:
                  'Export your completed forms in multiple formats with compression options',
              },
              {
                title: '24/7 Support',
                description:
                  'Our AI chatbot is always available to help you with any questions',
              },
            ].map((item, index) => (
              <div key={index} className="bg-white p-6 rounded-xl shadow-md">
                <h3 className="text-lg font-semibold text-primary-olive mb-2">
                  {item.title}
                </h3>
                <p className="text-gray-600 text-sm">{item.description}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="text-center bg-white p-12 rounded-3xl shadow-lg">
          <Users className="w-16 h-16 text-primary-blue mx-auto mb-6" />
          <h2 className="text-3xl font-bold text-primary-olive mb-4">
            Join Thousands of Happy Users
          </h2>
          <p className="text-gray-700 text-lg max-w-2xl mx-auto mb-8">
            People around the world trust AsaanForm to handle their important
            documents. Experience the future of form filling today.
          </p>
          <div className="flex justify-center items-center gap-4">
            <Heart className="w-6 h-6 text-primary-pink" />
            <span className="text-2xl font-bold text-primary-olive">
              Built with care for you
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};