export const normaliseFilenameForComparison = (filename) => {
  if (!filename) {
    return "";
  }

  return filename
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^0-9a-zA-Z._-]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+/, "")
    .replace(/^\.+/, "")
    .toLowerCase();
};

export default normaliseFilenameForComparison;
