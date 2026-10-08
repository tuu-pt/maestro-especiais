/** A small button that downloads a file from /api (the request says who is calling). */

import { useState } from "react";

import { download } from "../api/client";
import { Button, ErrorNote } from "./ui";

export function DownloadButton({ path, filename, children }: { path: string; filename: string; children: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <>
      <Button
        small
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setError(null);
          download(path, filename)
            .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao descarregar."))
            .finally(() => setBusy(false));
        }}
      >
        {children}
      </Button>
      {error ? <ErrorNote>{error}</ErrorNote> : null}
    </>
  );
}
