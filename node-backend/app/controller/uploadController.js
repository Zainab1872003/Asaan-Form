

// const Form = require("../models/form.model");
// const Document = require("../models/document.model");
// const axios = require("axios");
// const mongoose = require("mongoose");
// const FormData = require("form-data");

// const { uploadToGridFS, getFileStreamFromGridFS } = require("../utils/gridfs");

// const AI_BACKEND_URL = process.env.AI_BACKEND_URL || "http://localhost:8000";

// // ─── Helper: readable stream → Buffer ────────────────────────────────────────
// const streamToBuffer = (stream) =>
//   new Promise((resolve, reject) => {
//     const chunks = [];
//     stream.on("data", (c) => chunks.push(c));
//     stream.on("end", () => resolve(Buffer.concat(chunks)));
//     stream.on("error", reject);
//   });

// // ─── Helper: merge extractedData from all user documents ─────────────────────
// const mergeExtractedData = async (userId, latestData = {}) => {
//   const allDocs = await Document.find({ user: userId });
//   const merged = {};
//   for (const d of allDocs) {
//     if (d.extractedData && Object.keys(d.extractedData).length > 0) {
//       Object.assign(merged, d.extractedData);
//     }
//   }
//   Object.assign(merged, latestData); // latest doc wins
//   return merged;
// };

// // =============================================================================
// // 1. UPLOAD FORM
// // =============================================================================
// exports.uploadForm = async (req, res) => {
//   try {
//     if (!req.file) return res.status(400).json({ message: "No file uploaded" });

//     const { userID, formName } = req.body;
//     if (!userID) return res.status(400).json({ message: "userID is required" });

//     console.log(`[uploadForm] user=${userID} file=${req.file.originalname} size=${req.file.size}`);

//     // 1. Save original file to GridFS
//     const gridfsId = await uploadToGridFS(
//       req.file.buffer,
//       req.file.originalname,
//       req.file.mimetype,
//       { userId: userID, type: "form" }
//     );
//     console.log(`[uploadForm] ✅ GridFS: ${gridfsId}`);

//     // 2. Create Form record in MongoDB
//     const newForm = new Form({
//       user: userID,
//       formName: formName || req.file.originalname,
//       gridfsId,                           // ← GridFS file ID (for streaming)
//       filename: req.file.originalname,
//       contentType: req.file.mimetype,
//       status: "processing",
//     });
//     await newForm.save();
//     console.log(`[uploadForm] Form record: ${newForm._id}`);

//     // 3. Send bytes to AI for Docling field extraction
//     try {
//       const formData = new FormData();
//       formData.append("file", req.file.buffer, {
//         filename: req.file.originalname,
//         contentType: req.file.mimetype,
//       });

//       console.log(`[uploadForm] → AI: ${AI_BACKEND_URL}/form/upload/${userID} (${req.file.size} bytes)`);
//       const aiResponse = await axios.post(
//         `${AI_BACKEND_URL}/form/upload/${userID}`,
//         formData,
//         { headers: formData.getHeaders(), timeout: 300_000 }
//       );

//       const aiData = aiResponse.data?.data || aiResponse.data;
//       newForm.formIdAI = aiData?.form_id || aiResponse.data?.form_id;
//       newForm.formSchema =
//         aiData?.form_fields?.form_fields ||
//         aiResponse.data?.form_fields?.form_fields ||
//         [];
//       newForm.status = "ready";
//       await newForm.save();
//       console.log(`[uploadForm] ✅ formIdAI="${newForm.formIdAI}" fields=${newForm.formSchema.length}`);

//       return res.status(201).json({
//         message: "Form uploaded and processed successfully",
//         form: newForm,
//         aiResult: aiResponse.data,
//       });
//     } catch (aiError) {
//       console.error("[uploadForm] AI failed:", aiError.message);
//       newForm.status = "rejected";
//       await newForm.save();
//       return res.status(201).json({
//         message: "Form saved to GridFS but AI processing failed",
//         form: newForm,
//         error: aiError.message,
//       });
//     }
//   } catch (err) {
//     console.error("[uploadForm]", err.message);
//     res.status(500).json({ message: err.message });
//   }
// };

// // =============================================================================
// // 2. UPLOAD DOCUMENT (OCR only, no mapping)
// // =============================================================================
// exports.uploadDocument = async (req, res) => {
//   try {
//     if (!req.file) return res.status(400).json({ message: "No file uploaded" });

//     const { userID, documentType } = req.body;
//     if (!userID || !documentType)
//       return res.status(400).json({ message: "userID and documentType are required" });

//     // 1. Save to GridFS
//     const gridfsId = await uploadToGridFS(
//       req.file.buffer,
//       req.file.originalname,
//       req.file.mimetype,
//       { userId: userID, type: "document" }
//     );

//     // 2. Create Document record
//     const newDoc = new Document({
//       user: userID,
//       documentType,
//       gridfsId,
//       filename: req.file.originalname,
//       contentType: req.file.mimetype,
//       status: "processing",
//     });
//     await newDoc.save();

//     // 3. Send to AI for OCR + extraction
//     try {
//       const formData = new FormData();
//       formData.append("file", req.file.buffer, {
//         filename: req.file.originalname,
//         contentType: req.file.mimetype,
//       });

//       const aiResponse = await axios.post(
//         `${AI_BACKEND_URL}/document/upload/${userID}?document_type=${documentType}`,
//         formData,
//         { headers: formData.getHeaders(), timeout: 300_000 }
//       );

//       const aiData = aiResponse.data?.data || aiResponse.data;
//       newDoc.aiFilename = aiData?.file_info?.saved_filename || "";
//       newDoc.extractedData = aiData?.extracted || {};
//       newDoc.boundingBoxes = aiData?.ocr?.boxes || [];
//       newDoc.status = "ready";
//       await newDoc.save();

//       return res.status(201).json({
//         message: "Document processed successfully",
//         document: newDoc,
//         aiResult: aiResponse.data,
//       });
//     } catch (aiError) {
//       console.error("[uploadDocument] AI failed:", aiError.message);
//       newDoc.status = "rejected";
//       await newDoc.save();
//       return res.status(201).json({
//         message: "Document saved to GridFS but OCR failed",
//         document: newDoc,
//         error: aiError.message,
//       });
//     }
//   } catch (err) {
//     console.error("[uploadDocument]", err.message);
//     res.status(500).json({ message: err.message });
//   }
// };

// // =============================================================================
// // 3. UPLOAD AND MAP DOCUMENT
// //    Sends extractedData JSON to /fill/map-document (not filenames)
// // =============================================================================
// exports.uploadAndMapDocument = async (req, res) => {
//   try {
//     if (!req.file) return res.status(400).json({ message: "No file uploaded" });

//     const { userID, documentType, formID } = req.body;
//     if (!userID || !documentType || !formID)
//       return res.status(400).json({ message: "userID, documentType, and formID are required" });

//     const form = await Form.findById(formID);
//     if (!form) return res.status(404).json({ message: "Form not found" });

//     console.log(`[uploadAndMapDocument] user=${userID} type=${documentType} formID=${formID}`);
//     console.log(`[uploadAndMapDocument] form.formIdAI="${form.formIdAI}"`);

//     if (!form.formIdAI) {
//       return res.status(400).json({ message: "Form has not been processed by AI yet." });
//     }

//     // 1. Save to GridFS
//     const gridfsId = await uploadToGridFS(
//       req.file.buffer,
//       req.file.originalname,
//       req.file.mimetype,
//       { userId: userID, type: "document" }
//     );

//     // 2. Create Document record
//     const newDoc = new Document({
//       user: userID,
//       documentType,
//       formId: formID,
//       gridfsId,
//       filename: req.file.originalname,
//       contentType: req.file.mimetype,
//     });
//     await newDoc.save();
//     console.log(`[uploadAndMapDocument] Doc: ${newDoc._id}`);

//     // 3. Send to AI for OCR + extraction
//     const ocrFormData = new FormData();
//     ocrFormData.append("file", req.file.buffer, {
//       filename: req.file.originalname,
//       contentType: req.file.mimetype,
//     });

//     const procResponse = await axios.post(
//       `${AI_BACKEND_URL}/document/upload/${userID}?document_type=${documentType}`,
//       ocrFormData,
//       { headers: ocrFormData.getHeaders(), timeout: 300_000 }
//     );

//     const procData = procResponse.data?.data || procResponse.data;
//     const extractedData = procData?.extracted || {};
//     const ocrText = procData?.ocr?.english_text || procData?.ocr?.combined_text || "";

//     newDoc.aiFilename = procData?.file_info?.saved_filename || "";
//     newDoc.extractedData = extractedData;
//     console.log(`[uploadAndMapDocument] OCR ✅ fields=${Object.keys(extractedData).length}`);

//     // 4. Merge with all previous extractions for richer mapping
//     const mergedExtracted = await mergeExtractedData(userID, extractedData);
//     console.log(`[uploadAndMapDocument] Merged ${Object.keys(mergedExtracted).length} fields`);

//     // 5. Send merged JSON to AI for LLM semantic mapping
//     const mapData = new FormData();
//     mapData.append("user_id", userID);
//     mapData.append("form_id", form.formIdAI);
//     mapData.append("extracted_data", JSON.stringify(mergedExtracted));
//     mapData.append("ocr_text", ocrText);

//     const mapResponse = await axios.post(
//       `${AI_BACKEND_URL}/fill/map-document`,
//       mapData,
//       { headers: mapData.getHeaders(), timeout: 300_000 }
//     );

//     const filledFields = mapResponse.data?.filled_fields || [];
//     const missingKeys = mapResponse.data?.missing_keys || [];

//     newDoc.semanticMapping = filledFields;
//     await newDoc.save();
//     console.log(`[uploadAndMapDocument] Mapping ✅ ${filledFields.length} fields, ${missingKeys.length} missing`);

//     return res.status(201).json({
//       message: "Document uploaded, processed and mapped",
//       document: newDoc,
//       filled_fields: filledFields,
//       missing_keys: missingKeys,
//       chatbot_initial_prompt: mapResponse.data?.chatbot_initial_prompt || null,
//     });
//   } catch (err) {
//     console.error("[uploadAndMapDocument]", err.message);
//     if (err.response?.data) {
//       console.error("[uploadAndMapDocument] AI detail:", JSON.stringify(err.response.data).slice(0, 300));
//     }
//     res.status(500).json({ message: err.message });
//   }
// };

// // =============================================================================
// // 4. GET FILL DATA
// // =============================================================================
// exports.getFillData = async (req, res) => {
//   try {
//     const { formId, documentId } = req.params;
//     console.log(`[getFillData] formId=${formId} docId=${documentId}`);

//     const form = await Form.findById(formId);
//     const document = await Document.findById(documentId);

//     if (!form) return res.status(404).json({ message: "Form not found" });
//     if (!document) return res.status(404).json({ message: "Document not found" });

//     // Return cached mapping if it has values
//     if (document.semanticMapping && document.semanticMapping.length > 0) {
//       const hasValues = document.semanticMapping.some(
//         (m) => m.value != null && m.value !== ""
//       );
//       if (hasValues) {
//         console.log(`[getFillData] ✅ Cache: ${document.semanticMapping.length} fields`);
//         return res.status(200).json({
//           final_json: { form_id: form.formIdAI, fields: document.semanticMapping },
//           fields: document.semanticMapping,
//         });
//       }
//     }

//     // Not cached — run mapping now
//     const userID = document.user.toString();
//     const mergedExtracted = await mergeExtractedData(userID, document.extractedData || {});

//     if (Object.keys(mergedExtracted).length === 0) {
//       // Return empty form schema so frontend can still display the form
//       const emptyFields = (form.formSchema || []).map((f) => ({ ...f, value: null }));
//       console.log(`[getFillData] ⚠️ No extracted data — returning empty schema`);
//       return res.status(200).json({
//         final_json: { form_id: form.formIdAI, fields: emptyFields },
//         fields: emptyFields,
//         warning: "No document data found. Please upload a document.",
//       });
//     }

//     const mapData = new FormData();
//     mapData.append("user_id", userID);
//     mapData.append("form_id", form.formIdAI);
//     mapData.append("extracted_data", JSON.stringify(mergedExtracted));

//     const aiResponse = await axios.post(
//       `${AI_BACKEND_URL}/fill/map-document`,
//       mapData,
//       { headers: mapData.getHeaders(), timeout: 300_000 }
//     );

//     const fields = aiResponse.data?.filled_fields || [];
//     document.semanticMapping = fields;
//     await document.save();

//     console.log(`[getFillData] ✅ Mapped: ${fields.length} fields`);
//     return res.status(200).json({
//       final_json: { form_id: form.formIdAI, fields },
//       fields,
//     });
//   } catch (err) {
//     console.error("[getFillData]", err.message);
//     res.status(500).json({ message: err.message });
//   }
// };

// // =============================================================================
// // 5. GET FILLED PDF — streams form from GridFS → AI overlay → returns PDF
// // =============================================================================
// exports.getFilledPdf = async (req, res) => {
//   try {
//     const { formId, documentId } = req.params;
//     const form = await Form.findById(formId);
//     const document = await Document.findById(documentId);

//     if (!form) return res.status(404).json({ message: "Form not found" });
//     if (!document) return res.status(404).json({ message: "Document not found" });
//     if (!form.formIdAI) return res.status(400).json({ message: "Form not processed by AI yet" });

//     const fieldsToUse = document.semanticMapping || [];
//     if (fieldsToUse.length === 0) {
//       return res.status(400).json({ message: "No mapping found. View fill data first." });
//     }

//     // Stream original form PDF from GridFS using form.gridfsId
//     console.log(`[getFilledPdf] Streaming form from GridFS id=${form.gridfsId}`);
//     const formStream = getFileStreamFromGridFS(form.gridfsId.toString());
//     const formPdfBuffer = await streamToBuffer(formStream);
//     console.log(`[getFilledPdf] Got ${formPdfBuffer.length} bytes from GridFS`);

//     // Send to AI for PDF overlay
//     const formData = new FormData();
//     formData.append("user_id", document.user.toString());
//     formData.append("form_id", form.formIdAI);
//     formData.append("saved_mapping", JSON.stringify(fieldsToUse));
//     formData.append("form_file", formPdfBuffer, {
//       filename: form.filename || "form.pdf",
//       contentType: form.contentType || "application/pdf",
//     });

//     const aiResponse = await axios.post(
//       `${AI_BACKEND_URL}/fill/fill-existing`,
//       formData,
//       { headers: formData.getHeaders(), timeout: 300_000, responseType: "arraybuffer" }
//     );

//     const pdfBuffer = Buffer.from(aiResponse.data);
//     const safeName = (form.formName || "form")
//       .replace(/[^\w\-_. ]/g, "_")
//       .replace(/\s+/g, "_")
//       .slice(0, 100);

//     res.setHeader("Content-Type", "application/pdf");
//     res.setHeader("Content-Disposition", `attachment; filename="filled_${safeName}.pdf"`);
//     res.setHeader("Cache-Control", "no-store");
//     return res.send(pdfBuffer);
//   } catch (err) {
//     console.error("[getFilledPdf]", err.message);
//     res.status(500).json({ message: err.message });
//   }
// };

// // =============================================================================
// // 6. UPDATE MAPPING (manual edits from React)
// // =============================================================================
// exports.updateMapping = async (req, res) => {
//   try {
//     const { id } = req.params;
//     const { mapping, field_key, value } = req.body;

//     const doc = await Document.findById(id);
//     if (!doc) return res.status(404).json({ message: "Document not found" });

//     if (mapping && Array.isArray(mapping)) {
//       doc.semanticMapping = mapping;
//     } else if (field_key !== undefined && value !== undefined) {
//       const idx = doc.semanticMapping.findIndex((m) => m.field_key === field_key);
//       if (idx === -1)
//         return res.status(404).json({ message: `Field ${field_key} not found` });
//       doc.semanticMapping[idx].value = value;
//       doc.markModified("semanticMapping");
//     } else {
//       return res.status(400).json({
//         message: "Provide 'mapping' array OR 'field_key' + 'value'",
//       });
//     }

//     await doc.save();
//     return res.json({
//       message: "Mapping updated",
//       documentId: doc._id,
//       mapping: doc.semanticMapping,
//     });
//   } catch (err) {
//     console.error("[updateMapping]", err.message);
//     res.status(500).json({ message: err.message });
//   }
// };

// // =============================================================================
// // 7. LIST ENDPOINTS
// // =============================================================================
// exports.listUserForms = async (req, res) => {
//   try {
//     const forms = await Form.find({ user: req.params.userId })
//       .sort({ createdAt: -1 })
//       .lean();
//     res.status(200).json({ forms });
//   } catch (err) {
//     res.status(500).json({ message: err.message });
//   }
// };

// exports.listUserDocuments = async (req, res) => {
//   try {
//     const documents = await Document.find({ user: req.params.userId })
//       .sort({ createdAt: -1 })
//       .lean();
//     res.status(200).json({ documents });
//   } catch (err) {
//     res.status(500).json({ message: err.message });
//   }
// };

// // =============================================================================
// // 8. GET SINGLE RECORDS
// // =============================================================================
// exports.getForm = async (req, res) => {
//   try {
//     const form = await Form.findById(req.params.id);
//     if (!form) return res.status(404).json({ message: "Form not found" });
//     res.status(200).json({ form });
//   } catch (err) {
//     res.status(500).json({ message: err.message });
//   }
// };

// exports.getDocument = async (req, res) => {
//   try {
//     const doc = await Document.findById(req.params.id);
//     if (!doc) return res.status(404).json({ message: "Document not found" });
//     res.status(200).json({ document: doc });
//   } catch (err) {
//     res.status(500).json({ message: err.message });
//   }
// };

// // =============================================================================
// // 9. SERVE FILE FROM GRIDFS
// //
// // THE KEY FIX: The frontend sends the MongoDB Form/Document _id.
// // We look up the record to get its gridfsId, then stream from GridFS.
// // =============================================================================
// exports.getFile = async (req, res) => {
//   try {
//     const { fileId } = req.params;
//     console.log(`[getFile] requested fileId=${fileId}`);

//     let gridfsId = null;
//     let contentType = "application/octet-stream";
//     let filename = "file";

//     // fileId could be a MongoDB Form _id OR a MongoDB Document _id
//     // In both cases we need to find the record and get its .gridfsId

//     // Try Form first
//     const form = await Form.findById(fileId).catch(() => null);
//     if (form && form.gridfsId) {
//       gridfsId = form.gridfsId.toString();
//       contentType = form.contentType || contentType;
//       filename = form.filename || filename;
//       console.log(`[getFile] Found form → gridfsId=${gridfsId} file=${filename}`);
//     } else {
//       // Try Document
//       const doc = await Document.findById(fileId).catch(() => null);
//       if (doc && doc.gridfsId) {
//         gridfsId = doc.gridfsId.toString();
//         contentType = doc.contentType || contentType;
//         filename = doc.filename || filename;
//         console.log(`[getFile] Found document → gridfsId=${gridfsId} file=${filename}`);
//       }
//     }

//     // Last resort: maybe fileId IS already the gridfsId
//     if (!gridfsId) {
//       console.log(`[getFile] No record found for ${fileId}, trying as direct gridfsId`);
//       gridfsId = fileId;
//     }

//     const stream = getFileStreamFromGridFS(gridfsId);
//     res.setHeader("Content-Type", contentType);
//     res.setHeader("Content-Disposition", `inline; filename="${filename}"`);
//     stream.pipe(res);

//     stream.on("error", (err) => {
//       console.error(`[getFile] GridFS error: ${err.message}`);
//       if (!res.headersSent) {
//         res.status(404).json({ message: "File not found in GridFS" });
//       }
//     });
//   } catch (err) {
//     console.error("[getFile]", err.message);
//     if (!res.headersSent) {
//       res.status(500).json({ message: err.message });
//     }
//   }
// };


/**
 * uploadController.js — Final Stable Version
 *
 * Key guarantees:
 * - uploadAndMapDocument NEVER returns 500 — mapping failure = empty fields, user fills manually
 * - getFillData NEVER returns 500 — no data = empty schema returned
 * - getFile correctly resolves MongoDB _id → gridfsId before streaming
 */

const Form = require("../models/form.model");
const Document = require("../models/document.model");
const axios = require("axios");
const FormData = require("form-data");
const { uploadToGridFS, getFileStreamFromGridFS } = require("../utils/gridfs");

const AI_BACKEND_URL = process.env.AI_BACKEND_URL || "http://localhost:8000";

// ── stream → Buffer ───────────────────────────────────────────────────────────
const streamToBuffer = (stream) =>
  new Promise((resolve, reject) => {
    const chunks = [];
    stream.on("data", (c) => chunks.push(c));
    stream.on("end",  () => resolve(Buffer.concat(chunks)));
    stream.on("error", reject);
  });

// ── merge extractedData from all user documents ───────────────────────────────
const mergeExtractedData = async (userId, latestData = {}) => {
  const allDocs = await Document.find({ user: userId });
  const merged = {};
  for (const d of allDocs) {
    if (d.extractedData && Object.keys(d.extractedData).length > 0)
      Object.assign(merged, d.extractedData);
  }
  Object.assign(merged, latestData);
  return merged;
};

// =============================================================================
// 1. UPLOAD FORM
// =============================================================================
exports.uploadForm = async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ message: "No file uploaded" });
    const { userID, formName } = req.body;
    if (!userID) return res.status(400).json({ message: "userID is required" });

    console.log(`[uploadForm] user=${userID} file=${req.file.originalname} size=${req.file.size}`);

    const gridfsId = await uploadToGridFS(req.file.buffer, req.file.originalname, req.file.mimetype, { userId: userID, type: "form" });
    console.log(`[uploadForm] ✅ GridFS: ${gridfsId}`);

    const newForm = new Form({ user: userID, formName: formName || req.file.originalname, gridfsId, filename: req.file.originalname, contentType: req.file.mimetype, status: "processing" });
    await newForm.save();
    console.log(`[uploadForm] Form record: ${newForm._id}`);

    try {
      const fd = new FormData();
      fd.append("file", req.file.buffer, { filename: req.file.originalname, contentType: req.file.mimetype });
      console.log(`[uploadForm] → AI: ${AI_BACKEND_URL}/form/upload/${userID} (${req.file.size} bytes)`);
      const aiRes = await axios.post(`${AI_BACKEND_URL}/form/upload/${userID}`, fd, { headers: fd.getHeaders(), timeout: 300_000 });
      const aiData = aiRes.data?.data || aiRes.data;
      newForm.formIdAI   = aiData?.form_id || aiRes.data?.form_id;
      newForm.formSchema = aiData?.form_fields?.form_fields || aiRes.data?.form_fields?.form_fields || [];
      newForm.status     = "ready";
      await newForm.save();
      console.log(`[uploadForm] ✅ formIdAI="${newForm.formIdAI}" fields=${newForm.formSchema.length}`);
      return res.status(201).json({ message: "Form uploaded and processed successfully", form: newForm, aiResult: aiRes.data });
    } catch (aiErr) {
      console.error("[uploadForm] AI failed:", aiErr.message);
      newForm.status = "rejected";
      await newForm.save();
      return res.status(201).json({ message: "Form saved to GridFS but AI processing failed", form: newForm, error: aiErr.message });
    }
  } catch (err) {
    console.error("[uploadForm]", err.message);
    res.status(500).json({ message: err.message });
  }
};

// =============================================================================
// 2. UPLOAD DOCUMENT  (OCR only)
// =============================================================================
exports.uploadDocument = async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ message: "No file uploaded" });
    const { userID, documentType } = req.body;
    if (!userID || !documentType) return res.status(400).json({ message: "userID and documentType are required" });

    const gridfsId = await uploadToGridFS(req.file.buffer, req.file.originalname, req.file.mimetype, { userId: userID, type: "document" });
    const newDoc = new Document({ user: userID, documentType, gridfsId, filename: req.file.originalname, contentType: req.file.mimetype, status: "processing" });
    await newDoc.save();

    try {
      const fd = new FormData();
      fd.append("file", req.file.buffer, { filename: req.file.originalname, contentType: req.file.mimetype });
      const aiRes = await axios.post(`${AI_BACKEND_URL}/document/upload/${userID}?document_type=${documentType}`, fd, { headers: fd.getHeaders(), timeout: 300_000 });
      const aiData = aiRes.data?.data || aiRes.data;
      newDoc.aiFilename    = aiData?.file_info?.saved_filename || "";
      newDoc.extractedData = aiData?.extracted || {};
      newDoc.boundingBoxes = aiData?.ocr?.boxes || [];
      newDoc.status        = "ready";
      await newDoc.save();
      return res.status(201).json({ message: "Document processed successfully", document: newDoc, aiResult: aiRes.data });
    } catch (aiErr) {
      console.error("[uploadDocument] AI failed:", aiErr.message);
      newDoc.status = "rejected";
      await newDoc.save();
      return res.status(201).json({ message: "Document saved to GridFS but OCR failed", document: newDoc, error: aiErr.message });
    }
  } catch (err) {
    console.error("[uploadDocument]", err.message);
    res.status(500).json({ message: err.message });
  }
};

// =============================================================================
// 3. UPLOAD AND MAP DOCUMENT
//    NEVER returns 500 — if mapping fails, returns empty schema so frontend works
// =============================================================================
exports.uploadAndMapDocument = async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ message: "No file uploaded" });
    const { userID, documentType, formID } = req.body;
    if (!userID || !documentType || !formID) return res.status(400).json({ message: "userID, documentType, and formID are required" });

    const form = await Form.findById(formID);
    if (!form) return res.status(404).json({ message: "Form not found" });
    console.log(`[uploadAndMapDocument] user=${userID} type=${documentType} formID=${formID}`);
    console.log(`[uploadAndMapDocument] form.formIdAI="${form.formIdAI}"`);
    if (!form.formIdAI) return res.status(400).json({ message: "Form not processed by AI yet." });

    // 1. Save to GridFS
    const gridfsId = await uploadToGridFS(req.file.buffer, req.file.originalname, req.file.mimetype, { userId: userID, type: "document" });

    // 2. Create Document record
    const newDoc = new Document({ user: userID, documentType, formId: formID, gridfsId, filename: req.file.originalname, contentType: req.file.mimetype });
    await newDoc.save();
    console.log(`[uploadAndMapDocument] Doc: ${newDoc._id}`);

    // 3. OCR + extraction
    let extractedData = {};
    let ocrText = "";
    try {
      const fd = new FormData();
      fd.append("file", req.file.buffer, { filename: req.file.originalname, contentType: req.file.mimetype });
      const procRes = await axios.post(`${AI_BACKEND_URL}/document/upload/${userID}?document_type=${documentType}`, fd, { headers: fd.getHeaders(), timeout: 300_000 });
      const procData = procRes.data?.data || procRes.data;
      extractedData = procData?.extracted || {};
      ocrText       = procData?.ocr?.english_text || procData?.ocr?.combined_text || "";
      newDoc.aiFilename    = procData?.file_info?.saved_filename || "";
      newDoc.extractedData = extractedData;
    } catch (ocrErr) {
      console.warn(`[uploadAndMapDocument] OCR failed: ${ocrErr.message}`);
    }
    console.log(`[uploadAndMapDocument] OCR ✅ fields=${Object.keys(extractedData).length}`);

    // 4. Merge with previous extractions
    const mergedExtracted = await mergeExtractedData(userID, extractedData);
    console.log(`[uploadAndMapDocument] Merged ${Object.keys(mergedExtracted).length} fields`);

    // 5. Semantic mapping — failure is NOT fatal
    let filledFields  = [];
    let missingKeys   = [];
    let chatbotPrompt = null;

    try {
      const mapData = new FormData();
      mapData.append("user_id",        userID);
      mapData.append("form_id",        form.formIdAI);
      mapData.append("extracted_data", JSON.stringify(mergedExtracted));
      mapData.append("ocr_text",       ocrText);

      const mapRes  = await axios.post(`${AI_BACKEND_URL}/fill/map-document`, mapData, { headers: mapData.getHeaders(), timeout: 300_000 });
      filledFields  = mapRes.data?.filled_fields || [];
      missingKeys   = mapRes.data?.missing_keys  || [];
      chatbotPrompt = mapRes.data?.chatbot_initial_prompt || null;
      console.log(`[uploadAndMapDocument] Mapping ✅ ${filledFields.length} fields, ${missingKeys.length} missing`);
    } catch (mapErr) {
      // Graceful degradation: use empty form schema so frontend still renders
      console.warn(`[uploadAndMapDocument] ⚠️ Mapping failed: ${mapErr.message}`);
      filledFields = (form.formSchema || []).map(f => ({ ...f, value: null }));
      missingKeys  = filledFields;
    }

    newDoc.semanticMapping = filledFields;
    await newDoc.save();

    return res.status(201).json({
      message: filledFields.some(f => f.value != null)
        ? "Document uploaded, processed and mapped"
        : "Document uploaded. Fill fields manually or re-upload a clearer document.",
      document:              newDoc,
      filled_fields:         filledFields,
      missing_keys:          missingKeys,
      chatbot_initial_prompt: chatbotPrompt,
    });
  } catch (err) {
    console.error("[uploadAndMapDocument]", err.message);
    res.status(500).json({ message: err.message });
  }
};

// =============================================================================
// 4. GET FILL DATA
// =============================================================================
exports.getFillData = async (req, res) => {
  try {
    const { formId, documentId } = req.params;
    console.log(`[getFillData] formId=${formId} docId=${documentId}`);

    const form     = await Form.findById(formId);
    const document = await Document.findById(documentId);
    if (!form)     return res.status(404).json({ message: "Form not found" });
    if (!document) return res.status(404).json({ message: "Document not found" });

    // Return cached mapping if it has at least one non-null value
    if (document.semanticMapping?.length > 0) {
      const hasValues = document.semanticMapping.some(m => m.value != null && m.value !== "");
      if (hasValues) {
        console.log(`[getFillData] ✅ Cache: ${document.semanticMapping.length} fields`);
        return res.status(200).json({ final_json: { form_id: form.formIdAI, fields: document.semanticMapping }, fields: document.semanticMapping });
      }
    }

    // No cached values — run mapping
    const userID = document.user.toString();
    const mergedExtracted = await mergeExtractedData(userID, document.extractedData || {});

    if (Object.keys(mergedExtracted).length === 0) {
      const emptyFields = (form.formSchema || []).map(f => ({ ...f, value: null }));
      console.log(`[getFillData] ⚠️ No extracted data — returning empty schema`);
      return res.status(200).json({ final_json: { form_id: form.formIdAI, fields: emptyFields }, fields: emptyFields, warning: "No document data. Please upload a document." });
    }

    const mapData = new FormData();
    mapData.append("user_id",        userID);
    mapData.append("form_id",        form.formIdAI);
    mapData.append("extracted_data", JSON.stringify(mergedExtracted));
    const aiRes = await axios.post(`${AI_BACKEND_URL}/fill/map-document`, mapData, { headers: mapData.getHeaders(), timeout: 300_000 });
    const fields = aiRes.data?.filled_fields || [];
    document.semanticMapping = fields;
    await document.save();
    console.log(`[getFillData] ✅ Mapped: ${fields.length} fields`);
    return res.status(200).json({ final_json: { form_id: form.formIdAI, fields }, fields });
  } catch (err) {
    console.error("[getFillData]", err.message);
    res.status(500).json({ message: err.message });
  }
};

// =============================================================================
// 5. GET FILLED PDF — streams form from GridFS → AI overlay → returns PDF
// =============================================================================
exports.getFilledPdf = async (req, res) => {
  try {
    const { formId, documentId } = req.params;
    const form     = await Form.findById(formId);
    const document = await Document.findById(documentId);
    if (!form)         return res.status(404).json({ message: "Form not found" });
    if (!document)     return res.status(404).json({ message: "Document not found" });
    if (!form.formIdAI) return res.status(400).json({ message: "Form not processed by AI yet" });

    const fieldsToUse = document.semanticMapping || [];
    if (fieldsToUse.length === 0) return res.status(400).json({ message: "No mapping found. View fill data first." });

    console.log(`[getFilledPdf] Streaming form from GridFS id=${form.gridfsId}`);
    const formPdfBuffer = await streamToBuffer(getFileStreamFromGridFS(form.gridfsId.toString()));
    console.log(`[getFilledPdf] Got ${formPdfBuffer.length} bytes from GridFS`);

    const fd = new FormData();
    fd.append("user_id",      document.user.toString());
    fd.append("form_id",      form.formIdAI);
    fd.append("saved_mapping", JSON.stringify(fieldsToUse));
    fd.append("form_file",    formPdfBuffer, { filename: form.filename || "form.pdf", contentType: form.contentType || "application/pdf" });

    const aiRes = await axios.post(`${AI_BACKEND_URL}/fill/fill-existing`, fd, { headers: fd.getHeaders(), timeout: 300_000, responseType: "arraybuffer" });
    const safeName = (form.formName || "form").replace(/[^\w\-_. ]/g, "_").replace(/\s+/g, "_").slice(0, 100);
    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Disposition", `attachment; filename="filled_${safeName}.pdf"`);
    res.setHeader("Cache-Control", "no-store");
    return res.send(Buffer.from(aiRes.data));
  } catch (err) {
    console.error("[getFilledPdf]", err.message);
    res.status(500).json({ message: err.message });
  }
};

// =============================================================================
// 6. UPDATE MAPPING
// =============================================================================
exports.updateMapping = async (req, res) => {
  try {
    const { id } = req.params;
    const { mapping, field_key, value } = req.body;
    const doc = await Document.findById(id);
    if (!doc) return res.status(404).json({ message: "Document not found" });

    if (mapping && Array.isArray(mapping)) {
      doc.semanticMapping = mapping;
    } else if (field_key !== undefined && value !== undefined) {
      const idx = doc.semanticMapping.findIndex(m => m.field_key === field_key);
      if (idx === -1) return res.status(404).json({ message: `Field ${field_key} not found` });
      doc.semanticMapping[idx].value = value;
      doc.markModified("semanticMapping");
    } else {
      return res.status(400).json({ message: "Provide 'mapping' array OR 'field_key' + 'value'" });
    }

    await doc.save();
    return res.json({ message: "Mapping updated", documentId: doc._id, mapping: doc.semanticMapping });
  } catch (err) {
    console.error("[updateMapping]", err.message);
    res.status(500).json({ message: err.message });
  }
};

// =============================================================================
// 7. LIST
// =============================================================================
exports.listUserForms = async (req, res) => {
  try {
    res.status(200).json({ forms: await Form.find({ user: req.params.userId }).sort({ createdAt: -1 }).lean() });
  } catch (err) { res.status(500).json({ message: err.message }); }
};

exports.listUserDocuments = async (req, res) => {
  try {
    res.status(200).json({ documents: await Document.find({ user: req.params.userId }).sort({ createdAt: -1 }).lean() });
  } catch (err) { res.status(500).json({ message: err.message }); }
};

// =============================================================================
// 8. GET SINGLE RECORDS
// =============================================================================
exports.getForm = async (req, res) => {
  try {
    const form = await Form.findById(req.params.id);
    if (!form) return res.status(404).json({ message: "Form not found" });
    res.status(200).json({ form });
  } catch (err) { res.status(500).json({ message: err.message }); }
};

exports.getDocument = async (req, res) => {
  try {
    const doc = await Document.findById(req.params.id);
    if (!doc) return res.status(404).json({ message: "Document not found" });
    res.status(200).json({ document: doc });
  } catch (err) { res.status(500).json({ message: err.message }); }
};

// =============================================================================
// 9. SERVE FILE FROM GRIDFS
//    fileId = MongoDB Form._id or Document._id → look up gridfsId → stream
// =============================================================================
exports.getFile = async (req, res) => {
  try {
    const { fileId } = req.params;
    console.log(`[getFile] requested fileId=${fileId}`);

    let gridfsId    = null;
    let contentType = "application/octet-stream";
    let filename    = "file";

    const form = await Form.findById(fileId).catch(() => null);
    if (form?.gridfsId) {
      gridfsId = form.gridfsId.toString();
      contentType = form.contentType || contentType;
      filename    = form.filename    || filename;
      console.log(`[getFile] Found form → gridfsId=${gridfsId} file=${filename}`);
    } else {
      const doc = await Document.findById(fileId).catch(() => null);
      if (doc?.gridfsId) {
        gridfsId = doc.gridfsId.toString();
        contentType = doc.contentType || contentType;
        filename    = doc.filename    || filename;
        console.log(`[getFile] Found document → gridfsId=${gridfsId} file=${filename}`);
      }
    }

    if (!gridfsId) {
      console.log(`[getFile] No record for ${fileId}, trying as direct gridfsId`);
      gridfsId = fileId;
    }

    const stream = getFileStreamFromGridFS(gridfsId);
    res.setHeader("Content-Type", contentType);
    res.setHeader("Content-Disposition", `inline; filename="${filename}"`);
    stream.pipe(res);
    stream.on("error", (err) => {
      console.error(`[getFile] GridFS error: ${err.message}`);
      if (!res.headersSent) res.status(404).json({ message: "File not found in GridFS" });
    });
  } catch (err) {
    console.error("[getFile]", err.message);
    if (!res.headersSent) res.status(500).json({ message: err.message });
  }
};