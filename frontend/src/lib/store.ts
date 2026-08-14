import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface Patient {
  patient_id: string;
  pseudonym: string;
  age: number | null;
  sex: string;
  primary_condition: string | null;
  last_encounter_at: string | null;
  latest_data_watermark: string | null;
}

interface AppState {
  // Patient State
  selectedPatient: Patient | null;
  setSelectedPatient: (patient: Patient | null) => void;
  
  // Evidence/Citation Panel State
  focusedCitation: any | null; // Detailed citation object
  setFocusedCitation: (citation: any | null) => void;
  isEvidencePanelOpen: boolean;
  setEvidencePanelOpen: (isOpen: boolean) => void;

  // General App State
  clearPatientState: () => void;
  refreshTrigger: number;
  triggerRefresh: () => void;
  
  // Review Data
  currentReview: any | null;
  setCurrentReview: (review: any | null) => void;

  // User Preferences
  darkMode: boolean;
  setDarkMode: (value: boolean) => void;
  compactView: boolean;
  setCompactView: (value: boolean) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      selectedPatient: null,
      setSelectedPatient: (patient) => {
        // Khi chuyển bệnh nhân, phải xóa sạch state cũ (citation, panel)
        set((state) => {
          if (state.selectedPatient?.patient_id !== patient?.patient_id) {
            return { 
              selectedPatient: patient, 
              focusedCitation: null, 
              isEvidencePanelOpen: false,
              currentReview: null
            };
          }
          return { selectedPatient: patient };
        });
      },

      currentReview: null,
      setCurrentReview: (review) => set({ currentReview: review }),

      focusedCitation: null,
      setFocusedCitation: (citation) => set({ focusedCitation: citation, isEvidencePanelOpen: !!citation }),
      
      isEvidencePanelOpen: false,
      setEvidencePanelOpen: (isOpen) => set({ isEvidencePanelOpen: isOpen }),

      clearPatientState: () => set({
        selectedPatient: null,
        focusedCitation: null,
        isEvidencePanelOpen: false,
        currentReview: null
      }),
      refreshTrigger: 0,
      triggerRefresh: () => set((state) => ({ refreshTrigger: state.refreshTrigger + 1 })),

      // User Preferences default
      darkMode: true,
      setDarkMode: (value) => set({ darkMode: value }),
      compactView: false,
      setCompactView: (value) => set({ compactView: value })
    }),
    {
      name: 'app-preferences-storage',
      partialize: (state) => ({ darkMode: state.darkMode, compactView: state.compactView }),
    }
  )
);
