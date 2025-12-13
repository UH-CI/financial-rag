export function cleanStatuteValue(value: string): string {
  let parts = value.split(".").map((part: string) => { return part.replace(/^0+/, ''); });
  let stripped = parts.join(".");
  return stripped;
}