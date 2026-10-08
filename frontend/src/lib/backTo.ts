/** Where to go after signing in: only a path inside the application (never another site). */
export function backTo(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}
