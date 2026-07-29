/* Data hooks for the founder report. Each returns { data, loading, error } and
 * refetches when the report id changes. Screens stay declarative; all fetching,
 * auth and error handling lives in api.js. */
import { useEffect, useState } from 'react';
import { api } from '../lib/api';

function useApiResource(fetcher, deps) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let alive = true;
    const controller = new AbortController();
    setState({ data: null, loading: true, error: null });
    fetcher(controller.signal)
      .then((data) => alive && setState({ data, loading: false, error: null }))
      .catch((error) => {
        if (!alive || error.name === 'AbortError') return;
        setState({ data: null, loading: false, error });
      });
    return () => {
      alive = false;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}

/** Full report (all sections + facts). */
export function useReport(reportId) {
  return useApiResource(
    (signal) => api.reports.get(reportId, { signal }),
    [reportId]
  );
}

/** A single section slice — key is 'founder-dna' | 'business-dna' | 'recommendations'. */
export function useReportSection(reportId, section) {
  return useApiResource(
    (signal) => {
      const map = {
        'founder-dna': api.reports.founderDna,
        'business-dna': api.reports.businessDna,
        recommendations: api.reports.recommendations,
      };
      const fn = map[section] || api.reports.get;
      return fn(reportId, { signal });
    },
    [reportId, section]
  );
}
