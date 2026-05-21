export function messageFromError(err: unknown) {
  return err instanceof Error ? err.message : "Something went wrong";
}
