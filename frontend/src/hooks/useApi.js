import { useCallback, useEffect, useState } from 'react';

/**
 * Run an API call and track loading/error state.
 *
 * `deps` behaves like a useEffect dependency list: change them and the call
 * re-runs. `reload` re-runs it on demand, which the pages use after training.
 */
export function useApi(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    fetcher()
      .then((result) => active && setData(result))
      .catch((err) => active && setError(err))
      .finally(() => active && setLoading(false));

    // Ignore results from a request that has been superseded.
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  return { data, error, loading, reload };
}
