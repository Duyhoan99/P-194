'use client';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

const STATUS_MAP: Record<string, { className: string; label: string }> = {
  DRAFT: { className: 'badge-draft', label: 'Bản nháp' },
  NEEDS_REVISION: { className: 'badge-needs-revision', label: 'Cần chỉnh sửa' },
  REJECTED: { className: 'badge-rejected', label: 'Từ chối' },
  APPROVED: { className: 'badge-approved', label: 'Đã duyệt' },
  EXPORTED: { className: 'badge-exported', label: 'Đã xuất' },
  SUCCESS: { className: 'badge-success', label: 'Thành công' },
  PARTIAL: { className: 'badge-warning', label: 'Một phần' },
  EMPTY: { className: 'badge-info', label: 'Trống' },
  DENIED: { className: 'badge-error', label: 'Từ chối truy cập' },
  NOT_LOADED: { className: 'badge-warning', label: 'Chưa tải' },
  ACTIVE: { className: 'badge-success', label: 'Hoạt động' },
  LOCKED: { className: 'badge-error', label: 'Đã khóa' },
  VALID: { className: 'badge-success', label: 'Hợp lệ' },
  INVALID: { className: 'badge-error', label: 'Không hợp lệ' },
  UNSUPPORTED: { className: 'badge-warning', label: 'Không hỗ trợ' },
  UNRESOLVED: { className: 'badge-warning', label: 'Chưa giải quyết' },
  RESOLVED: { className: 'badge-success', label: 'Đã giải quyết' },
  ALLOW: { className: 'badge-success', label: 'Cho phép' },
  DENY: { className: 'badge-error', label: 'Từ chối' },
  ERROR: { className: 'badge-error', label: 'Lỗi' },
};

export default function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const mapped = STATUS_MAP[status] || { className: 'badge-info', label: status };

  return (
    <span
      className={`badge ${mapped.className}`}
      style={size === 'sm' ? { fontSize: 11, padding: '2px 8px' } : undefined}
    >
      {mapped.label}
    </span>
  );
}
