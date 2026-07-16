---
name: imagegen-fix
description: Generate images through the imagegen skill when explicitly requested, then recover, save, and display the built-in image_generation_call Base64 result; also recover and display existing image-generation results when the chat UI did not render them. Use when users ask this skill to generate and show an image, ask where a generated image is, report a missing generated image, request the raw imagegen result, or when an image_generation_call contains a non-empty result even if its status is still generating.
---

# Imagegen Fix

Generate only when the user explicitly asks this skill to make a new image. Otherwise recover the existing image result instead of generating a duplicate. Treat a non-empty Base64 `result` that decodes to a valid image as success; do not treat `status: generating` alone as failure.

## Modes

- **Generate then recover**: When the user's current request is a new image prompt and they invoked this skill to produce it, first use the `imagegen` skill in its default built-in tool mode. After the built-in `image_gen` call returns, immediately run this skill's recovery script to decode the selected inline Base64 result into `outputs/`, validate it, and embed the saved file with an absolute Markdown image path.
- **Recover existing result**: When the user asks where a generated image is, says the image did not show, asks for the raw result, or refers to a prior generation, do not generate again. Recover the matching existing `image_generation_call` result from the session log.

## Workflow

1. Decide the mode from the user's current request.
2. In generate-then-recover mode, read and follow the `imagegen` skill. Use the built-in `image_gen` path unless that skill requires an explicit fallback. Preserve the user's prompt intent and any constraints.
3. Do not regenerate merely because the tool result looks blank or its status is `generating`.
4. Run `scripts/recover_imagegen_result.py` to locate an `image_generation_call` with a non-empty `result`, decode it, validate its file signature, and save it in the current workspace.
5. Prefer an explicit session log with `--log` when known. Otherwise let the script scan recent `$CODEX_HOME/sessions/**/*.jsonl` files.
6. When concurrent image tasks may exist, select the intended result with `--image-id` or a distinctive `--prompt-contains` value from the just-used prompt. If the built-in result exposes an image ID, prefer `--image-id`.
7. Save user-facing files under the current workspace's `outputs/` directory. Use `--raw-json` only when the user asks for the complete underlying response.
8. Inspect the decoded file with `view_image` when visual verification is needed.
9. Embed the recovered image in the final response with an absolute Markdown image path and provide a download link.

## Commands

Recover the newest valid result:

```powershell
python "<skill-dir>\scripts\recover_imagegen_result.py" `
  --out "<workspace>\outputs\imagegen-result.png"
```

Select a result by prompt and preserve the complete raw response:

```powershell
python "<skill-dir>\scripts\recover_imagegen_result.py" `
  --prompt-contains "orange tabby cat" `
  --out "<workspace>\outputs\orange-tabby-cat.png" `
  --raw-json "<workspace>\outputs\imagegen-full-return.jsonl"
```

Use `--log <session.jsonl>` when the current session log is already known. The script prints a JSON summary containing the selected image ID, source log, format, decoded byte count, Base64 length, and SHA-256 hash without printing the Base64 itself.

## Success Criteria

Declare recovery successful only when all of these are true:

- `payload.result` is a non-empty Base64 string.
- Base64 decoding succeeds.
- The decoded bytes have a recognized PNG, JPEG, WebP, or GIF signature.
- The output file is written successfully.

Ignore `status: generating` when these criteria pass. Report failure when no matching result exists or validation fails.

For generate-then-recover mode, do not issue a second image generation if recovery fails after a completed built-in `image_gen` call. Report the recovery failure and the selection criteria used, then ask whether to regenerate only if a new image is actually needed.

## Output Rules

- Do not paste multi-megabyte Base64 data into chat. Save the complete raw record to a file when requested.
- Do not expose unrelated task records. Export only the selected image-generation record.
- Do not search generated-image folders as the primary test; inline image results may exist only in the session record.
- Do not regenerate in recovery-only mode unless the user explicitly requests another image.
- On Windows, use an absolute renderable Markdown path such as `![image](/C:/path/to/image.png)`.
