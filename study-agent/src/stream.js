export function takeNdjsonLines(remainder, chunk) {
  const lines = `${remainder}${chunk}`.split("\n");
  const nextRemainder = lines.pop() || "";
  const events = lines.filter((line) => line.trim()).map((line) => JSON.parse(line));
  return { events, remainder: nextRemainder };
}
