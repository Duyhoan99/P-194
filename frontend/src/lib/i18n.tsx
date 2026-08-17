'use client';
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

type Language = 'en' | 'vi';

const translations = {
  en: {
    // Sidebar
    'nav.dashboard': 'Dashboard',
    'nav.caseFiles': 'Case Files',
    'nav.patients': 'Patients',
    'nav.analytics': 'Analytics',
    'nav.settings': 'Settings',
    'nav.help': 'Help',
    'nav.recentPatients': 'Recent Patients',
    'nav.logout': 'Logout',

    // Dashboard
    'dash.title': 'Dashboard',
    'dash.subtitle': 'System overview and patient metrics',
    'dash.totalPatients': 'Total Patients',
    'dash.recentUploads': 'Recent Uploads',
    'dash.activeReviews': 'Active Reviews',
    'dash.systemStatus': 'System Status',
    'dash.operational': 'Operational',
    'dash.checking': 'Checking...',
    'dash.viewAll': 'View all',
    'dash.noPatients': 'No patients found',
    'dash.noUploads': 'No uploads found',
    'dash.searchPatients': 'Search patients...',
    'dash.searchDocs': 'Search documents...',

    // Settings
    'set.title': 'Settings',
    'set.subtitle': 'Configure your workspace and AI preferences',
    'set.save': 'Save Changes',
    'set.nav.profile': 'Profile & Account',
    'set.nav.notify': 'Notifications',
    'set.nav.security': 'Security & Privacy',
    'set.nav.ai': 'AI Models & Data',
    'set.personal': 'Personal Information',
    'set.fullName': 'Full Name',
    'set.email': 'Email Address',
    'set.role': 'Role',
    'set.systemPref': 'System Preferences',
    'set.darkMode': 'Dark Mode',
    'set.darkModeDesc': 'Use dark theme across the clinical workspace',
    'set.compact': 'Compact View',
    'set.compactDesc': 'Reduce padding to fit more information on screen',
    'set.lang': 'Language',
    'set.langDesc': 'Switch between English and Vietnamese',
    'set.danger': 'Danger Zone',
    'set.dangerDesc': 'Permanent actions that cannot be undone.',
    'set.deleteAcc': 'Delete Account',

    // Patient Deletion
    'pt.delete': 'Delete Patient',
    'pt.deleteConfirm': 'Are you sure you want to delete this patient?',
    'pt.deleteDesc': 'This will permanently delete all data, documents, and history associated with this patient.',
    'pt.deleteSuccess': 'Patient deleted successfully',
    'pt.deleteError': 'Failed to delete patient',
    'common.cancel': 'Cancel',
    'common.confirm': 'Confirm',
    'cf.quota': 'Storage Quota',

    // Help
    'help.title': 'How can we help?',
    'help.subtitle': 'Search our knowledge base or get in touch with our support team for any technical or clinical assistance.',
    'help.search': 'Search documentation, FAQs, and guides...',
    'help.docs': 'Documentation',
    'help.docsDesc': 'Read comprehensive guides on using the Clinical Intelligence Workspace.',
    'help.docsAction': 'Read Docs',
    'help.chat': 'Live Chat',
    'help.chatDesc': 'Chat with our support team during standard business hours.',
    'help.chatAction': 'Start Chat',
    'help.email': 'Email Support',
    'help.emailDesc': 'Send us a detailed request and we\'ll reply within 24 hours.',
    'help.emailAction': 'Send Email',
    'help.faq': 'Frequently Asked Questions',

    // Patients
    'pt.title': 'Patient Directory',
    'pt.subtitle': 'Browse and manage all patient profiles',
    'pt.search': 'Search patients by name or ID...',
    'pt.notFound': 'No patients found',
    'pt.trySearch': 'Try adjusting your search or upload a new patient document.',

    // Analytics
    'an.title': 'Analytics',
    'an.subtitle': 'System performance and clinical data insights',
    'an.totalConsult': 'Total Consultations',
    'an.docsProcessed': 'Documents Processed',
    'an.accuracy': 'Processing Accuracy',
    'an.avgTime': 'Average Processing Time',
    'an.volume': 'Processing Volume (Demo)',
    'an.types': 'Document Types (Demo)',
    'an.lab': 'Lab Results',
    'an.clinical': 'Clinical Notes',
    'an.imaging': 'Imaging Reports',
    'an.prescription': 'Prescriptions',
  },
  vi: {
    // Sidebar
    'nav.dashboard': 'Tổng quan',
    'nav.caseFiles': 'Hồ sơ',
    'nav.patients': 'Bệnh nhân',
    'nav.analytics': 'Phân tích',
    'nav.settings': 'Cài đặt',
    'nav.help': 'Trợ giúp',
    'nav.recentPatients': 'Bệnh nhân gần đây',
    'nav.logout': 'Đăng xuất',

    // Dashboard
    'dash.title': 'Tổng quan',
    'dash.subtitle': 'Tổng quan hệ thống và các chỉ số bệnh nhân',
    'dash.totalPatients': 'Tổng số bệnh nhân',
    'dash.recentUploads': 'Tài liệu mới tải lên',
    'dash.activeReviews': 'Đang đánh giá',
    'dash.systemStatus': 'Trạng thái hệ thống',
    'dash.operational': 'Đang hoạt động',
    'dash.checking': 'Đang kiểm tra...',
    'dash.viewAll': 'Xem tất cả',
    'dash.noPatients': 'Không tìm thấy bệnh nhân',
    'dash.noUploads': 'Không tìm thấy tài liệu',
    'dash.searchPatients': 'Tìm kiếm bệnh nhân...',
    'dash.searchDocs': 'Tìm kiếm tài liệu...',

    // Settings
    'set.title': 'Cài đặt',
    'set.subtitle': 'Cấu hình không gian làm việc và AI',
    'set.save': 'Lưu thay đổi',
    'set.nav.profile': 'Hồ sơ & Tài khoản',
    'set.nav.notify': 'Thông báo',
    'set.nav.security': 'Bảo mật & Quyền riêng tư',
    'set.nav.ai': 'Mô hình AI & Dữ liệu',
    'set.personal': 'Thông tin cá nhân',
    'set.fullName': 'Họ và tên',
    'set.email': 'Địa chỉ Email',
    'set.role': 'Vai trò',
    'set.systemPref': 'Tuỳ chọn hệ thống',
    'set.darkMode': 'Chế độ tối',
    'set.darkModeDesc': 'Sử dụng giao diện tối cho toàn hệ thống',
    'set.compact': 'Giao diện nhỏ gọn',
    'set.compactDesc': 'Giảm khoảng cách để hiển thị nhiều thông tin hơn',
    'set.lang': 'Ngôn ngữ',
    'set.langDesc': 'Chuyển đổi giữa Tiếng Anh và Tiếng Việt',
    'set.danger': 'Khu vực nguy hiểm',
    'set.dangerDesc': 'Những hành động vĩnh viễn không thể hoàn tác.',
    'set.deleteAcc': 'Xóa tài khoản',

    // Patient Deletion
    'pt.delete': 'Xóa bệnh nhân',
    'pt.deleteConfirm': 'Bạn có chắc chắn muốn xóa bệnh nhân này?',
    'pt.deleteDesc': 'Hành động này sẽ xóa toàn bộ dữ liệu, tài liệu, và lịch sử của bệnh nhân. Không thể hoàn tác.',
    'pt.deleteSuccess': 'Đã xóa bệnh nhân thành công',
    'pt.deleteError': 'Lỗi khi xóa bệnh nhân',
    'common.cancel': 'Hủy',
    'common.confirm': 'Xác nhận',
    'cf.quota': 'Dung lượng lưu trữ',

    // Help
    'help.title': 'Chúng tôi có thể giúp gì?',
    'help.subtitle': 'Tìm kiếm trong cơ sở kiến thức hoặc liên hệ đội ngũ hỗ trợ.',
    'help.search': 'Tìm kiếm tài liệu, câu hỏi thường gặp...',
    'help.docs': 'Tài liệu hướng dẫn',
    'help.docsDesc': 'Đọc các hướng dẫn chi tiết về cách sử dụng hệ thống.',
    'help.docsAction': 'Đọc tài liệu',
    'help.chat': 'Trò chuyện trực tiếp',
    'help.chatDesc': 'Chat với đội ngũ hỗ trợ trong giờ hành chính.',
    'help.chatAction': 'Bắt đầu Chat',
    'help.email': 'Hỗ trợ Email',
    'help.emailDesc': 'Gửi yêu cầu chi tiết và chúng tôi sẽ phản hồi trong 24 giờ.',
    'help.emailAction': 'Gửi Email',
    'help.faq': 'Câu hỏi thường gặp',

    // Patients
    'pt.title': 'Danh sách bệnh nhân',
    'pt.subtitle': 'Quản lý toàn bộ hồ sơ bệnh nhân',
    'pt.search': 'Tìm kiếm bệnh nhân theo tên hoặc ID...',
    'pt.notFound': 'Không tìm thấy bệnh nhân',
    'pt.trySearch': 'Thử tìm kiếm khác hoặc tải lên hồ sơ mới.',

    // Analytics
    'an.title': 'Phân tích',
    'an.subtitle': 'Hiệu suất hệ thống và dữ liệu lâm sàng',
    'an.totalConsult': 'Tổng số ca khám',
    'an.docsProcessed': 'Tài liệu đã xử lý',
    'an.accuracy': 'Độ chính xác',
    'an.avgTime': 'Thời gian xử lý trung bình',
    'an.volume': 'Lưu lượng xử lý (Mô phỏng)',
    'an.types': 'Loại tài liệu (Mô phỏng)',
    'an.lab': 'Kết quả xét nghiệm',
    'an.clinical': 'Ghi chú lâm sàng',
    'an.imaging': 'Kết quả hình ảnh',
    'an.prescription': 'Đơn thuốc',
  }
};

type Translations = typeof translations.en;
type TranslationKey = keyof Translations;

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: TranslationKey) => string;
}

const LanguageContext = createContext<LanguageContextType>({
  language: 'en',
  setLanguage: () => { },
  t: (key) => translations.en[key] || key,
});

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>('en');

  useEffect(() => {
    const saved = localStorage.getItem('app_language') as Language;
    if (saved === 'vi' || saved === 'en') {
      setLanguageState(saved);
    } else {
      // Auto detect based on browser logic (optional, we default to vi for this project or keep en)
      // Since it's a Vietnamese team let's default to vi, or stick to saved
      setLanguageState('en');
    }
  }, []);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem('app_language', lang);
  };

  const t = (key: TranslationKey): string => {
    return translations[language][key] || key;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
