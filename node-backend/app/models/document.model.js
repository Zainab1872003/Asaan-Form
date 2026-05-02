const mongoose = require("mongoose");

const documentSchema = new mongoose.Schema({
  user: {
    type: mongoose.Schema.Types.ObjectId,
    ref: "User",
    required: true,
    index: true,
  },
  documentType: {
    type: String,
    required: true,
  },
  // ── GridFS storage ──────────────────────────────────────────────────────
  gridfsId: {
    type: mongoose.Schema.Types.ObjectId,
    required: true,
  },
  filename: {
    type: String,         // original filename (e.g. "my_cnic.pdf")
  },
  contentType: String,

  // ── AI backend reference ────────────────────────────────────────────────
  // The AI backend generates a unique internal filename for its temp file.
  // Stored here so we can reference it in logs. NOT used for storage lookups.
  aiFilename: {
    type: String,
    default: "",
  },

  // ── Extracted data (from AI OCR + LLM) ─────────────────────────────────
  extractedData: {
    type: mongoose.Schema.Types.Mixed,
    default: {},
  },
  boundingBoxes: {
    type: Array,
    default: [],
  },

  // ── Semantic mapping (filled form fields) ──────────────────────────────
  semanticMapping: {
    type: Array,          // Array of { field_key, field_name, field_type, value, coordinates, page_number }
    default: [],
  },

  // ── Relationships ───────────────────────────────────────────────────────
  formId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: "Form",
    default: null,
  },

  // ── Status ──────────────────────────────────────────────────────────────
  status: {
    type: String,
    enum: ["processing", "ready", "rejected"],
    default: "processing",
  },

  createdAt: {
    type: Date,
    default: Date.now,
  },
});

// Virtual so chatbotController can use doc.originalName
documentSchema.virtual("originalName").get(function () {
  return this.filename || this.documentType || "document";
});

documentSchema.set("toJSON", { virtuals: true });
documentSchema.set("toObject", { virtuals: true });

const Document = mongoose.model("Document", documentSchema);
module.exports = Document;