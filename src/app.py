"""
Template Demo for IBM Granite Hugging Face spaces.

UPDATED:
- Auto-load images from /data/images
- Prompts include:
  - Describe image
  - Convert to DoclingDocument JSON (with picture classification + picture description)
- GPU memory cap to ~80% (best-effort)
- DoclingDocument JSON export is JSON-safe (AnyUrl -> str)
- When requested:
  - picture description: add to doc.pictures[*].captions
  - picture classification: add as 'CLASSIFICATION: ...' to captions
"""

import html
import json
import os
import random
import re
import time
from pathlib import Path
from threading import Thread
from typing import Optional

import gradio as gr
import numpy as np
import spaces
import torch
from docling_core.types.doc import DoclingDocument
from docling_core.types.doc.document import DocTagsDocument
from PIL import Image, ImageDraw, ImageOps
from transformers import AutoProcessor, Idefics3ForConditionalGeneration, TextIteratorStreamer
try:
    from transformers.generation.stopping_criteria import StoppingCriteria, StoppingCriteriaList
except Exception:
    # older layout fallback
    from transformers.generation_stopping_criteria import StoppingCriteria, StoppingCriteriaList
from themes.research_monochrome import theme

dir_ = Path(__file__).parent.parent

TITLE = "Granite-docling-258m demo"

DESCRIPTION = """
<p>This experimental demo highlights the capabilities of granite-docling-258M for document conversion.</p>
<p>Updated to support: (1) image descriptions, (2) DoclingDocument JSON export with picture classification/description prompts.</p>
"""

device = torch.device(
    "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
)

# =========================
# Limit GPU to ~80% (best-effort)
# =========================
if torch.cuda.is_available():
    try:
        torch.cuda.set_per_process_memory_fraction(0.80, device=0)
    except Exception:
        pass

# =========================
# Auto-load images from folder
# =========================
SAMPLES_PATH = dir_ / "data" / "images"

image_files = sorted(
    list(SAMPLES_PATH.glob("*.png")) + list(SAMPLES_PATH.glob("*.jpg")) + list(SAMPLES_PATH.glob("*.jpeg"))
)

# =========================
# Prompts
# =========================
DEFAULT_PROMPTS = [
    "Describe this image in detail.",
    "List the main objects and their locations.",
    "Summarize the scene in one sentence.",
    # --- DoclingDocument JSON prompts ---
    "Convert this page to DoclingDocument JSON.",
    "Convert this page to DoclingDocument JSON with picture classification enabled.",
    "Convert this page to DoclingDocument JSON with picture description enabled.",
    "Convert this page to DoclingDocument JSON with picture classification AND picture description enabled.",
]


def _pretty_name(p: Path) -> str:
    return p.stem.replace("_", " ").replace("-", " ").strip().title()


if image_files:
    sample_data = [
        {
            "preview_image": str(p),
            "prompts": DEFAULT_PROMPTS,
            "image": str(p),
            "name": _pretty_name(p),
            "pad": False,
        }
        for p in image_files
    ]
else:
    # Fallback so the app doesn't crash if folder is empty
    sample_data = [
        {
            "preview_image": str(SAMPLES_PATH / "new_arxiv.png"),
            "prompts": DEFAULT_PROMPTS,
            "image": str(SAMPLES_PATH / "new_arxiv.png"),
            "name": "Sample Image",
            "pad": False,
        }
    ]

# Initialize the model
model_id = "ibm-granite/granite-docling-258M"

if gr.NO_RELOAD:
    processor = AutoProcessor.from_pretrained(model_id, local_files_only=True)
    model = Idefics3ForConditionalGeneration.from_pretrained(
        model_id,
        local_files_only=True,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    ).to(device)


def add_random_padding(image: Image.Image, min_percent: float = 0.1, max_percent: float = 0.10) -> Image.Image:
    image = image.convert("RGB")
    width, height = image.size
    pad_w = int(width * random.uniform(min_percent, max_percent))
    pad_h = int(height * random.uniform(min_percent, max_percent))
    corner_pixel = image.getpixel((0, 0))
    return ImageOps.expand(image, border=(pad_w, pad_h, pad_w, pad_h), fill=corner_pixel)


def draw_bounding_boxes(image_path: str, response_text: str, is_doctag_response: bool = False) -> Image.Image:
    try:
        image = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(image)
        width, height = image.size

        class_colors = {
            "picture": "#FFCCA4",
            "chart": "#FFCCA4",
            "table": "#FFCCCC",
            "text": "#FFFF99",
            "title": "#FF9999",
            "section_header": "#FF9999",
            "code": "#7D7D7D",
            "caption": "#FFCC99",
        }

        doctag_class_pattern = r"<([^>]+)><loc_(\d+)><loc_(\d+)><loc_(\d+)><loc_(\d+)>[^<]*</[^>]+>"
        doctag_matches = re.findall(doctag_class_pattern, response_text)

        class_pattern = r"<([^>]+)><loc_(\d+)><loc_(\d+)><loc_(\d+)><loc_(\d+)>"
        class_matches = re.findall(class_pattern, response_text)

        seen = set()
        all_matches = []
        for match in doctag_matches:
            coords = (match[1], match[2], match[3], match[4])
            if coords not in seen:
                seen.add(coords)
                all_matches.append(match)
        for match in class_matches:
            coords = (match[1], match[2], match[3], match[4])
            if coords not in seen:
                seen.add(coords)
                all_matches.append(match)

        for class_name, xmin, ymin, xmax, ymax in all_matches:
            color = class_colors.get(class_name.lower(), "#808080") if is_doctag_response else "#E0115F"
            x1 = int((int(xmin) / 500) * width)
            y1 = int((int(ymin) / 500) * height)
            x2 = int((int(xmax) / 500) * width)
            y2 = int((int(ymax) / 500) * height)
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

        return image
    except Exception:
        return Image.open(image_path)


def clean_model_response(text: str) -> str:
    if not text:
        return "No response generated."
    for token in ["<|end_of_text|>", "<|end|>", "<|assistant|>", "<|user|>", "<|system|>", "<pad>", "</s>", "<s>"]:
        text = text.replace(token, "")
    return text.strip() or "The model generated an empty response."


_streaming_raw_output = ""
STOP_PROCESSING = False  # Stop button sets this to True

class StopOnFlag(StoppingCriteria):
    def __call__(self, input_ids, scores, **kwargs) -> bool:
        return STOP_PROCESSING

def _wants_docling_json(msg: str) -> bool:
    m = msg.lower()
    return (
        ("doclingdocument" in m)
        or ("docling document" in m)
        or ("doclingdocument json" in m)
        or ("docling json" in m)
    )


def _wants_picture_description(msg: str) -> bool:
    m = msg.lower()
    return "picture description" in m or "description enabled" in m


def _wants_picture_classification(msg: str) -> bool:
    m = msg.lower()
    return "picture classification" in m or "classification enabled" in m


def _docling_prompt_wrapped(msg: str) -> str:
    """
    Force the model to respond in doctag/docling-friendly format when user asks for DoclingDocument JSON.
    """
    m = msg.lower()
    wants_class = "classification" in m
    wants_desc = ("picture description" in m) or ("description enabled" in m)

    flags = []
    if wants_class:
        flags.append("picture classification")
    if wants_desc:
        flags.append("picture description")

    if flags:
        flag_text = " and ".join(flags)
        return (
            "Convert this page to doctags suitable for DoclingDocument conversion. "
            f"Include {flag_text} for each picture element if possible. "
            "Return doctags only."
        )

    return "Convert this page to doctags suitable for DoclingDocument conversion. Return doctags only."


@spaces.GPU()
def generate_with_model_streaming(question: str, image_path: str, apply_padding: bool = False):
    global _streaming_raw_output, STOP_PROCESSING
    STOP_PROCESSING = False  # reset at start of generation
    _streaming_raw_output = ""

    image = Image.open(image_path).convert("RGB")
    if apply_padding:
        image = add_random_padding(image)

    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": question}]}]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True)

    inputs = processor(text=prompt, images=[image], return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    streamer = TextIteratorStreamer(processor, skip_prompt=True, skip_special_tokens=False)

    generation_args = dict(
        inputs,
        streamer=streamer,
        max_new_tokens=768,
        do_sample=False,
        pad_token_id=processor.tokenizer.eos_token_id,
        stopping_criteria=StoppingCriteriaList([StopOnFlag()]),
    )

    thread = Thread(target=model.generate, kwargs=generation_args)
    thread.start()

    yield "..."
    full_output = ""
    escaped = ""
    for new_text in streamer:
        if STOP_PROCESSING:
            break
        full_output += new_text
        escaped += html.escape(new_text)
        yield escaped

    _streaming_raw_output = full_output


def _generate_one_shot(prompt_text: str, image_path: str, apply_padding: bool = False, max_new_tokens: int = 128) -> str:
    """
    Small deterministic helper for short classification/description.
    """
    image = Image.open(image_path).convert("RGB")
    if apply_padding:
        image = add_random_padding(image)

    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt_text}]}]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True)

    inputs = processor(text=prompt, images=[image], return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        out_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=processor.tokenizer.eos_token_id,
        )

    txt = processor.batch_decode(out_ids[:, inputs["input_ids"].shape[1] :], skip_special_tokens=False)[0]
    return clean_model_response(txt)


def _add_picture_enrichment(doc: DoclingDocument, image_path: str, want_desc: bool, want_class: bool) -> None:
    """
    Safe enrichment: inject into PictureItem.captions where supported.
    Works even if docling-core schema differs slightly across versions.
    """
    if not (want_desc or want_class):
        return

    desc: Optional[str] = None
    cls: Optional[str] = None

    if want_desc:
        desc = _generate_one_shot(
            "Write a concise description of the picture content in 1-2 sentences. No XML, no tags.",
            image_path,
            apply_padding=False,
            max_new_tokens=128,
        )

    if want_class:
        cls = _generate_one_shot(
            "Classify this image into ONE label: photo, chart, diagram, table, text_page, map, other. Reply with label only.",
            image_path,
            apply_padding=False,
            max_new_tokens=16,
        ).splitlines()[0].strip()

    pics = getattr(doc, "pictures", None)
    if not pics:
        return

    for pic in pics:
        # Prefer captions list if present
        if hasattr(pic, "captions"):
            caps = getattr(pic, "captions") or []
            # Ensure list
            if not isinstance(caps, list):
                caps = [str(caps)]
            if cls:
                caps.append(f"CLASSIFICATION: {cls}")
            if desc:
                caps.append(desc)
            setattr(pic, "captions", caps)
        else:
            # Fallback: try to attach to a generic "meta" dict if exists
            if hasattr(pic, "meta") and isinstance(getattr(pic, "meta"), dict):
                meta = getattr(pic, "meta")
                if cls:
                    meta["classification"] = cls
                if desc:
                    meta["description"] = desc
                setattr(pic, "meta", meta)


chatbot = gr.Chatbot(
    examples=[{"text": x} for x in sample_data[0]["prompts"]],
    type="messages",
    label=f"Q&A about {sample_data[0]['name']}",
    height=685,
    group_consecutive_messages=True,
    autoscroll=False,
    elem_classes=["chatbot_view"],
)

css_file_path = Path(Path(__file__).parent / "app.css")
head_file_path = Path(Path(__file__).parent / "app_head.html")

with gr.Blocks(fill_height=True, css_paths=css_file_path, head_paths=head_file_path, theme=theme, title=TITLE) as demo:
    is_in_edit_mode = gr.State(True)
    selected_doc = gr.State(0)
    current_question = gr.State("")
    uploaded_image_path = gr.State(None)

    with gr.Row():
        gr.Markdown(f"# {TITLE}")
        stop_btn = gr.Button("⛔ Stop Processing")
    gr.Markdown(DESCRIPTION)

    def stop_generation():
        global STOP_PROCESSING
        STOP_PROCESSING = True

    stop_btn.click(stop_generation)

    gallery_with_captions = [(sd["preview_image"], sd["name"]) for sd in sample_data]

    document_gallery = gr.Gallery(
        gallery_with_captions,
        label="Select a document",
        rows=1,
        columns=9,
        height="125px",
        allow_preview=False,
        selected_index=0,
        elem_classes=["preview_im_element"],
        show_label=True,
    )

    with gr.Row():
        with gr.Column(), gr.Group():
            image_display = gr.Image(
                sample_data[0]["image"],
                label=f"Preview for {sample_data[0]['name']}",
                height=700,
                interactive=False,
                elem_classes=["image_viewer"],
            )
            upload_button = gr.UploadButton(
                "📁 Upload Image", file_types=["image"], elem_classes=["upload_button"], scale=1
            )

        with gr.Column():
            chatbot.render()
            with gr.Row():
                tbb = gr.Textbox(submit_btn=True, show_label=False, placeholder="Type a message...", scale=4)
                fb = gr.Button("Ask new question", visible=False, scale=1)
            fb.click(lambda: [], outputs=[chatbot])

    def sample_image_selected(d: gr.SelectData):
        dx = sample_data[d.index]
        return (
            gr.update(examples=[{"text": x} for x in dx["prompts"]], label=f"Q&A about {dx['name']}"),
            gr.update(value=dx["image"], label=f"Preview for {dx['name']}"),
            d.index,
        )

    document_gallery.select(lambda: [], outputs=[chatbot])
    document_gallery.select(sample_image_selected, inputs=[], outputs=[chatbot, image_display, selected_doc])

    def question_from_selection(x: gr.SelectData) -> str:
        return x.value["text"]

    def handle_image_upload(uploaded_file: str | None):
        if uploaded_file is None:
            return None, None, None
        image_update = gr.update(value=uploaded_file, label="Uploaded Image")
        chatbot_update = gr.update(examples=[{"text": DEFAULT_PROMPTS[0]}], label="Q&A about uploaded image")
        return image_update, chatbot_update, [], uploaded_file

    upload_button.upload(
        handle_image_upload,
        inputs=[upload_button],
        outputs=[image_display, chatbot, chatbot, uploaded_image_path],
    )

    def send_generate(msg: str, cb: list, selected_sample: int, uploaded_img_path: str | None = None):
        image_path = uploaded_img_path if uploaded_img_path is not None else sample_data[selected_sample]["image"]
        cb.append(gr.ChatMessage(role="user", content=msg))
        cb.append(gr.ChatMessage(role="assistant", content="..."))
        yield cb, gr.update()

        apply_padding = False if uploaded_img_path is not None else sample_data[selected_sample].get("pad", False)

        # If user wants DoclingDocument JSON, force a docling/doctags response
        actual_prompt = _docling_prompt_wrapped(msg) if _wants_docling_json(msg) else msg

        # Stream
        try:
            stream_gen = generate_with_model_streaming(actual_prompt.strip(), image_path, apply_padding)
            for partial in stream_gen:
                cb[-1] = gr.ChatMessage(role="assistant", content=partial)
                yield cb, gr.update()
        except Exception as e:
            cb[-1] = gr.ChatMessage(role="assistant", content=f"Error: {e!s}")
            yield cb, gr.update()

        # Finalize output
        answer_raw = html.unescape(_streaming_raw_output) if _streaming_raw_output else cb[-1].content
        answer = clean_model_response(answer_raw)

        # If DoclingDocument requested: convert doctags -> DoclingDocument -> JSON (+ enrichment)
        if _wants_docling_json(msg):
            want_desc = _wants_picture_description(msg)
            want_class = _wants_picture_classification(msg)

            try:
                doctags_doc = DocTagsDocument.from_doctags_and_image_pairs([answer], [Image.open(image_path)])
                doc = DoclingDocument.load_from_doctags(doctags_doc, document_name="Document")

                # Add picture enrichment AFTER conversion (reliable)
                _add_picture_enrichment(doc, image_path=image_path, want_desc=want_desc, want_class=want_class)

                # JSON-safe dump
                try:
                    doc_dict = doc.model_dump(mode="json")  # pydantic v2
                except TypeError:
                    doc_dict = doc.dict()  # pydantic v1
                doc_json = json.dumps(doc_dict, indent=2, ensure_ascii=False, default=str)

                cb[-1] = gr.ChatMessage(role="assistant", content=f"```json\n{doc_json}\n```")
            except Exception as e:
                cb[-1] = gr.ChatMessage(
                    role="assistant",
                    content=(
                        "Failed to build DoclingDocument JSON from doctags.\n\n"
                        f"Error: {e!s}\n\nRaw output:\n```xml\n{answer}\n```"
                    ),
                )
            yield cb, gr.update(value=image_path)
            return

        # Otherwise: normal response (description, etc.)
        cb[-1] = gr.ChatMessage(role="assistant", content=answer)

        # Optional: keep bbox overlay if loc tags appear
        class_loc_pattern = r"<([^>]+)><loc_(\d+)><loc_(\d+)><loc_(\d+)><loc_(\d+)>"
        loc_only_pattern = r"<loc_(\d+)><loc_(\d+)><loc_(\d+)><loc_(\d+)>"
        has_loc_tags = re.findall(class_loc_pattern, answer) or re.findall(loc_only_pattern, answer)
        has_doctag = "<doctag>" in answer

        if has_loc_tags:
            try:
                annotated = draw_bounding_boxes(image_path, answer, is_doctag_response=has_doctag)
                yield cb, gr.update(value=np.array(annotated), visible=True)
            except Exception:
                yield cb, gr.update(value=image_path)
        else:
            yield cb, gr.update(value=image_path)

    chatbot.example_select(lambda: False, outputs=is_in_edit_mode)
    chatbot.example_select(question_from_selection, inputs=[], outputs=[current_question]).then(
        send_generate,
        inputs=[current_question, chatbot, selected_doc, uploaded_image_path],
        outputs=[chatbot, image_display],
    )

    def textbox_switch(e_mode: bool):
        return [gr.update(visible=bool(e_mode)), gr.update(visible=not bool(e_mode))]

    tbb.submit(lambda: False, outputs=[is_in_edit_mode])
    fb.click(lambda: True, outputs=[is_in_edit_mode])
    is_in_edit_mode.change(textbox_switch, inputs=[is_in_edit_mode], outputs=[tbb, fb])

    tbb.submit(lambda x: x, inputs=[tbb], outputs=[current_question]).then(
        send_generate,
        inputs=[current_question, chatbot, selected_doc, uploaded_image_path],
        outputs=[chatbot, image_display],
    )

if __name__ == "__main__":
    demo.queue(max_size=20)
    demo.launch()