"use client";
import { createContext, useContext, useState, useCallback, ReactNode } from "react";

type ToastType = "success" | "warning" | "danger" | "info";
interface ToastItem { id: string; message: string; type: ToastType; }

const ToastContext = createContext<{ show: (msg: string, type?: ToastType) => void }>({ show: () => {} });
export const useToast = () => useContext(ToastContext);

export function ToastContainer({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const show = useCallback((message: string, type: ToastType = "info") => {
    const id = Math.random().toString(36).slice(2);
    setToasts(t => [...t, { id, message, type }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 5000);
  }, []);
  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="ds-toast-container">
        {toasts.map(t => (
          <div key={t.id} className="ds-toast" role="alert">
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function Toast({ message, type = "info" }: { message: string; type?: ToastType }) {
  return <div className="ds-toast" role="alert"><span>{message}</span></div>;
}
