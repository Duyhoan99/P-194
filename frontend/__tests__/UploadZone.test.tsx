import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import UploadZone from '@/components/UploadZone';
import { ingestions } from '@/lib/api';

const mockTriggerRefresh = jest.fn();
let mockSelectedPatient: { patient_id: string } | null = { patient_id: 'PAT-001' };

jest.mock('@/lib/api', () => ({
  ingestions: {
    upload: jest.fn(),
    getStatus: jest.fn(),
  },
}));

jest.mock('@/lib/store', () => ({
  useAppStore: () => ({
    selectedPatient: mockSelectedPatient,
    triggerRefresh: mockTriggerRefresh,
  }),
}));

const uploadMock = ingestions.upload as jest.Mock;

function chooseFiles(container: HTMLElement) {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  const files = [
    new File(['first'], 'first.pdf', { type: 'application/pdf', lastModified: 1 }),
    new File(['second'], 'second.json', { type: 'application/json', lastModified: 2 }),
  ];
  fireEvent.change(input, { target: { files } });
}

beforeEach(() => {
  jest.clearAllMocks();
  mockSelectedPatient = { patient_id: 'PAT-001' };
});

test('uploads every selected file into the selected patient', async () => {
  uploadMock
    .mockResolvedValueOnce({ batch_id: 'batch-1', patient_id: 'PAT-001', status: 'completed' })
    .mockResolvedValueOnce({ batch_id: 'batch-2', patient_id: 'PAT-001', status: 'completed' });
  const { container } = render(<UploadZone />);

  chooseFiles(container);
  fireEvent.click(screen.getByRole('button', { name: 'Tải lên 2 tệp' }));

  await waitFor(() => expect(uploadMock).toHaveBeenCalledTimes(2));
  expect(uploadMock.mock.calls[0][1]).toBe('PAT-001');
  expect(uploadMock.mock.calls[1][1]).toBe('PAT-001');
  expect(await screen.findAllByText('completed')).toHaveLength(2);
});

test('reuses the patient created by the first file for remaining files', async () => {
  mockSelectedPatient = null;
  uploadMock
    .mockResolvedValueOnce({ batch_id: 'batch-1', patient_id: 'PAT-NEW-ABC123', status: 'completed' })
    .mockResolvedValueOnce({ batch_id: 'batch-2', patient_id: 'PAT-NEW-ABC123', status: 'completed' });
  const { container } = render(<UploadZone />);

  fireEvent.change(screen.getByLabelText('Hồ sơ bệnh nhân đích'), {
    target: { value: 'new' },
  });
  fireEvent.change(screen.getByLabelText('Tên bệnh nhân mới'), {
    target: { value: 'Nguyễn Văn A' },
  });
  chooseFiles(container);
  fireEvent.click(screen.getByRole('button', { name: 'Tải lên 2 tệp' }));

  await waitFor(() => expect(uploadMock).toHaveBeenCalledTimes(2));
  expect(uploadMock.mock.calls[0][1]).toBeUndefined();
  expect(uploadMock.mock.calls[0][3]).toBe('Nguyễn Văn A');
  expect(uploadMock.mock.calls[1][1]).toBe('PAT-NEW-ABC123');
  expect(uploadMock.mock.calls[1][3]).toBeUndefined();
});
