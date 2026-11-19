/** SHA-256 en hexadecimal con Web Crypto. El archivo nunca sale del navegador. */
export async function sha256Hex(datos: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", datos);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

export const mismoHash = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();
