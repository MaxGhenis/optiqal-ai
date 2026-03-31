"use client";

import { useEffect, useRef } from "react";

interface ActiveRequest {
  id: number;
  controller: AbortController;
}

export function useLatestRequest() {
  const requestSeqRef = useRef(0);
  const activeRequestRef = useRef<ActiveRequest | null>(null);

  useEffect(() => {
    return () => {
      activeRequestRef.current?.controller.abort();
    };
  }, []);

  function beginRequest(): {
    requestId: number;
    controller: AbortController;
    supersededPrevious: boolean;
  } {
    const requestId = requestSeqRef.current + 1;
    requestSeqRef.current = requestId;
    const supersededPrevious = activeRequestRef.current !== null;
    activeRequestRef.current?.controller.abort();

    const controller = new AbortController();
    activeRequestRef.current = {
      id: requestId,
      controller,
    };

    return {
      requestId,
      controller,
      supersededPrevious,
    };
  }

  function isCurrentRequest(requestId: number): boolean {
    return activeRequestRef.current?.id === requestId;
  }

  function finishRequest(requestId: number): boolean {
    if (!isCurrentRequest(requestId)) {
      return false;
    }
    activeRequestRef.current = null;
    return true;
  }

  return {
    beginRequest,
    isCurrentRequest,
    finishRequest,
  };
}
