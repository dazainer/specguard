import { useEffect } from 'react';

/** Per-route document title so browser history, tabs and screen readers identify the page. */
export function useDocumentTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} · SpecGuard` : 'SpecGuard';
  }, [title]);
}
