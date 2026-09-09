import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Run an API call and track loading, error and data.
 *
 * `deps` behaves like a useEffect dependency list. `reload` re-runs on demand.
 * Results from a superseded request are discarded, so fast filter typing cannot
 * leave an older response on screen.
 */
export function useApi(fetcher, deps = [], options = {}) {
  const { enabled = true, initialData = null } = options;

  const [data, setData] = useState(initialData);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [nonce, setNonce] = useState(0);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return undefined;
    }

    let active = true;
    setLoading(true);
    setError(null);

    fetcherRef
      .current()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err) => {
        if (active) setError(err);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce, enabled]);

  return { data, error, loading, reload, setData };
}

/**
 * Run a mutation and track its in-flight and error state.
 *
 * Keeps try/catch/setLoading out of every submit handler, and guarantees the
 * button re-enables even when the request fails.
 */
export function useMutation(mutator) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const mutate = useCallback(
    async (...args) => {
      setLoading(true);
      setError(null);
      try {
        return await mutator(...args);
      } catch (err) {
        setError(err);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [mutator],
  );

  return { mutate, loading, error, reset: () => setError(null) };
}
