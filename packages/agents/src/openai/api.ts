import { Language } from "./lang";

// ============================================================================
// Transcription Models
// ============================================================================

/** OpenAI transcription model IDs */
export const MODEL_WHISPER_1 = "whisper-1" as const;
export const MODEL_GPT_4O_TRANSCRIBE = "gpt-4o-transcribe" as const;
export const MODEL_GPT_4O_MINI_TRANSCRIBE = "gpt-4o-mini-transcribe" as const;
export const MODEL_GPT_4O_TRANSCRIBE_DIARIZE = "gpt-4o-transcribe-diarize" as const;

/** Union type of all OpenAI transcription models */
export type TranscriptionModel =
  | typeof MODEL_WHISPER_1
  | typeof MODEL_GPT_4O_TRANSCRIBE
  | typeof MODEL_GPT_4O_MINI_TRANSCRIBE
  | typeof MODEL_GPT_4O_TRANSCRIBE_DIARIZE;

/** All transcription models as an array (for runtime validation) */
export const TRANSCRIPTION_MODELS = [
  MODEL_WHISPER_1,
  MODEL_GPT_4O_TRANSCRIBE,
  MODEL_GPT_4O_MINI_TRANSCRIBE,
  MODEL_GPT_4O_TRANSCRIBE_DIARIZE,
] as const;

/** Type guard for TranscriptionModel */
export function isTranscriptionModel(value: unknown): value is TranscriptionModel {
  return typeof value === "string" && TRANSCRIPTION_MODELS.includes(value as TranscriptionModel);
}

// ============================================================================
// Audio Response Format
// ============================================================================

/** Audio response format values */
export const RESPONSE_FORMAT_JSON = "json" as const;
export const RESPONSE_FORMAT_TEXT = "text" as const;
export const RESPONSE_FORMAT_SRT = "srt" as const;
export const RESPONSE_FORMAT_VERBOSE_JSON = "verbose_json" as const;
export const RESPONSE_FORMAT_VTT = "vtt" as const;
export const RESPONSE_FORMAT_DIARIZED_JSON = "diarized_json" as const;

/** Union type of all audio response formats */
export type AudioResponseFormat =
  | typeof RESPONSE_FORMAT_JSON
  | typeof RESPONSE_FORMAT_TEXT
  | typeof RESPONSE_FORMAT_SRT
  | typeof RESPONSE_FORMAT_VERBOSE_JSON
  | typeof RESPONSE_FORMAT_VTT
  | typeof RESPONSE_FORMAT_DIARIZED_JSON;

/** All audio response formats as an array */
export const AUDIO_RESPONSE_FORMATS = [
  RESPONSE_FORMAT_JSON,
  RESPONSE_FORMAT_TEXT,
  RESPONSE_FORMAT_SRT,
  RESPONSE_FORMAT_VERBOSE_JSON,
  RESPONSE_FORMAT_VTT,
  RESPONSE_FORMAT_DIARIZED_JSON,
] as const;

/** Type guard for AudioResponseFormat */
export function isAudioResponseFormat(value: unknown): value is AudioResponseFormat {
  return typeof value === "string" && AUDIO_RESPONSE_FORMATS.includes(value as AudioResponseFormat);
}

// ============================================================================
// Transcription Include
// ============================================================================

/** Transcription include values */
export const TRANSCRIPTION_INCLUDE_LOGPROBS = "logprobs" as const;

/** Union type of transcription include options */
export type TranscriptionInclude = typeof TRANSCRIPTION_INCLUDE_LOGPROBS;

/** All transcription include options as an array */
export const TRANSCRIPTION_INCLUDES = [TRANSCRIPTION_INCLUDE_LOGPROBS] as const;

/** Type guard for TranscriptionInclude */
export function isTranscriptionInclude(value: unknown): value is TranscriptionInclude {
  return (
    typeof value === "string" && TRANSCRIPTION_INCLUDES.includes(value as TranscriptionInclude)
  );
}

// ============================================================================
// Timestamp Granularity
// ============================================================================

/** Timestamp granularity values */
export const TIMESTAMP_GRANULARITY_WORD = "word" as const;
export const TIMESTAMP_GRANULARITY_SEGMENT = "segment" as const;

/** Union type of timestamp granularities */
export type TimestampGranularity =
  | typeof TIMESTAMP_GRANULARITY_WORD
  | typeof TIMESTAMP_GRANULARITY_SEGMENT;

/** All timestamp granularities as an array */
export const TIMESTAMP_GRANULARITIES = [
  TIMESTAMP_GRANULARITY_WORD,
  TIMESTAMP_GRANULARITY_SEGMENT,
] as const;

/** Type guard for TimestampGranularity */
export function isTimestampGranularity(value: unknown): value is TimestampGranularity {
  return (
    typeof value === "string" && TIMESTAMP_GRANULARITIES.includes(value as TimestampGranularity)
  );
}

// ============================================================================
// Create Transcription Request
// ============================================================================

/** Request body for creating a transcription */
export interface CreateTranscriptionRequest {
  /** The audio file to transcribe (Blob/File in browser, Buffer in Node) */
  file: Blob | ArrayBuffer;

  /** ID of the model to use */
  model: TranscriptionModel;

  /** The language of the input audio in ISO-639-1 format */
  language?: Language;

  /** Optional text to guide the model's style or continue a previous audio segment */
  prompt?: string;

  /** The format of the output */
  response_format?: AudioResponseFormat;

  /** Sampling temperature between 0 and 1 */
  temperature?: number;

  /** Additional information to include in the response */
  include?: TranscriptionInclude[];

  /** Timestamp granularities to populate (requires verbose_json format) */
  timestamp_granularities?: TimestampGranularity[];

  /** If true, stream the response using server-sent events (not supported for whisper-1) */
  stream?: boolean | null;
}
