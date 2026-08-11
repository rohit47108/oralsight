export type TemporaryBase64FileIo = {
  writeBase64(uri: string, value: string): Promise<void>;
  delete(uri: string): Promise<void>;
};

export async function writeTemporaryBase64File(
  destination: string,
  value: string,
  io: TemporaryBase64FileIo,
): Promise<void> {
  try {
    await io.writeBase64(destination, value);
  } catch (writeError) {
    try {
      await io.delete(destination);
    } catch {
      throw new Error(
        "Temporary file cleanup failed after an incomplete write.",
        {
          cause: writeError,
        },
      );
    }
    throw writeError;
  }
}
