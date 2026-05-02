
/**
 * utils/gridfs.js
 *
 * GridFS helper utilities for Node.js backend.
 * The AI backend should NEVER import or use these — storage is Node.js only.
 */

const { getGridFSBucket } = require("../config/db.config");
const mongoose = require("mongoose");

/**
 * Upload a file buffer to GridFS.
 *
 * @param {Buffer}  buffer      - File content
 * @param {string}  filename    - Original filename (used for display)
 * @param {string}  contentType - MIME type
 * @param {Object}  metadata    - Extra metadata stored with the file
 * @returns {Promise<mongoose.Types.ObjectId>} GridFS file _id
 */
const uploadToGridFS = (buffer, filename, contentType, metadata = {}) => {
  const bucket = getGridFSBucket();

  return new Promise((resolve, reject) => {
    const uploadStream = bucket.openUploadStream(filename, {
      contentType,
      metadata: {
        ...metadata,
        uploadedAt: new Date(),
        originalName: filename,
      },
    });

    uploadStream.end(buffer);
    uploadStream.on("finish", () => resolve(uploadStream.id));
    uploadStream.on("error", reject);
  });
};

/**
 * Get a readable stream for a file stored in GridFS.
 *
 * @param {string|mongoose.Types.ObjectId} fileId
 * @returns {GridFSBucketReadStream}
 */
const getFileStreamFromGridFS = (fileId) => {
  const bucket = getGridFSBucket();
  const objectId =
    fileId instanceof mongoose.Types.ObjectId
      ? fileId
      : new mongoose.Types.ObjectId(String(fileId));
  return bucket.openDownloadStream(objectId);
};

/**
 * Delete a file from GridFS.
 *
 * @param {string|mongoose.Types.ObjectId} fileId
 */
const deleteFromGridFS = async (fileId) => {
  const bucket = getGridFSBucket();
  const objectId =
    fileId instanceof mongoose.Types.ObjectId
      ? fileId
      : new mongoose.Types.ObjectId(String(fileId));
  await bucket.delete(objectId);
};

/**
 * Check whether a file exists in GridFS.
 *
 * @param {string|mongoose.Types.ObjectId} fileId
 * @returns {Promise<boolean>}
 */
const existsInGridFS = async (fileId) => {
  const bucket = getGridFSBucket();
  const objectId =
    fileId instanceof mongoose.Types.ObjectId
      ? fileId
      : new mongoose.Types.ObjectId(String(fileId));
  const files = await bucket.find({ _id: objectId }).toArray();
  return files.length > 0;
};

module.exports = {
  uploadToGridFS,
  getFileStreamFromGridFS,
  deleteFromGridFS,
  existsInGridFS,
};