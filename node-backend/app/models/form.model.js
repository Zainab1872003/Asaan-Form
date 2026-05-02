const mongoose = require("mongoose");

const formSchema = new mongoose.Schema({
  user: {
    type: mongoose.Schema.Types.ObjectId,
    ref: "User",
    required: true,
    index: true,
  },
  formName: {
    type: String,
    required: true,
  },
  // ── GridFS storage ──────────────────────────────────────────────────────
  gridfsId: {
    type: mongoose.Schema.Types.ObjectId,
    required: true,
  },
  filename: String,       // original filename (e.g. "admission_form.pdf")
  contentType: String,

  // ── AI backend reference ────────────────────────────────────────────────
  formIdAI: {
    type: String,         // AI backend internal folder name (e.g. "20260329_204622_b560...")
  },

  // ── Extracted form schema ───────────────────────────────────────────────
  formSchema: {
    type: Array,          // Array of form field objects with coordinates
    default: [],
  },

  // ── Status ──────────────────────────────────────────────────────────────
  status: {
    type: String,
    enum: ["draft", "processing", "ready", "rejected"],
    default: "draft",
  },

  createdAt: {
    type: Date,
    default: Date.now,
  },
});

const Form = mongoose.model("Form", formSchema);
module.exports = Form;