/**
 * uploadRoutes.js
 * All upload, mapping, PDF generation and file-serving routes.
 */

const express = require("express");
const router = express.Router();
const uploadController = require("../controller/uploadController");
const { upload } = require("../config/db.config");

// ── Form ─────────────────────────────────────────────────────────────────────
router.post("/form", upload.single("file"), uploadController.uploadForm);
router.get("/form/:id", uploadController.getForm);
router.get("/forms/user/:userId", uploadController.listUserForms);

// ── Document ─────────────────────────────────────────────────────────────────
router.post("/document", upload.single("file"), uploadController.uploadDocument);
router.post("/document/map", upload.single("file"), uploadController.uploadAndMapDocument);
router.get("/document/:id", uploadController.getDocument);
router.get("/documents/user/:userId", uploadController.listUserDocuments);

// ── Fill / Mapping ────────────────────────────────────────────────────────────
router.get("/form/:formId/document/:documentId/fill-data", uploadController.getFillData);
router.get("/form/:formId/document/:documentId/filled-pdf", uploadController.getFilledPdf);
router.put("/document/mapping/:id", uploadController.updateMapping);

// ── File serving (GridFS) ─────────────────────────────────────────────────────
router.get("/file/:fileId", uploadController.getFile);

module.exports = router;