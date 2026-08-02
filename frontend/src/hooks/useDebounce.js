import { useEffect, useState } from 'react';

/**
 * Debounce a rapidly-changing value.
 *
 * Used for the admin search box: typing "alice" would otherwise fire five
 * requests, and they can come back out of order — so the list would briefly show
 * results for "alic" after those for "alice". Debouncing sends one request for the
 * settled value instead.
 */
export function useDebounce(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);   // a new keystroke cancels the pending update
  }, [value, delay]);

  return debounced;
}

export default useDebounce;
