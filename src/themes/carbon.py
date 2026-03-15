"""IBM Carbon theme for gradio demos.

This version builds on top of the Carbon theme to make it more playful with rounded corners, a larger font family to
enhance readability, and the IBM Cool Gray color palette for better consistency with other IBM Research demos, such as
Bee.
"""

import gradio as gr
from gradio.themes.utils import sizes

theme = gr.themes.Base(
    primary_hue=gr.themes.Color(
        c100="#EDF5FF",
        c200="#D0E2FF",
        c300="#A6C8FF",
        c400="#78A9FF",
        c50="#F9F9FB",
        c500="#4589FF",
        c600="#0F62FE",
        c700="#0043CE",
        c800="#002D9C",
        c900="#001D6C",
        c950="#001141",
    ),
    secondary_hue=gr.themes.Color(
        c100="#EDF5FF",
        c200="#D0E2FF",
        c300="#A6C8FF",
        c400="#78A9FF",
        c50="#F9F9FB",
        c500="#4589FF",
        c600="#0F62FE",
        c700="#0043CE",
        c800="#002D9C",
        c900="#001D6C",
        c950="#001141",
    ),
    neutral_hue=gr.themes.Color(
        c100="#F2F4F8",
        c200="#DDE1E6",
        c300="#C1C7CD",
        c400="#A2A9B0",
        c50="#F9F9FB",
        c500="#878D96",
        c600="#697077",
        c700="#4D5358",
        c800="#393939",
        c900="#21272A",
        c950="#121619",
    ),
    spacing_size=sizes.spacing_md,  # change spacing to default size
    radius_size=sizes.radius_md,  # change spacing to default size and Keep Radius to make demo feel more playful
    text_size=sizes.text_lg,  # change fontsize to default size
    #   spacing_size: sizes.Size | str = sizes.spacing_md,  #change spacing to default size
    #         radius_size: sizes.Size | str = sizes.radius_md, #change spacing to default size and Keep Radius to make
    #                                                           demo feel more playful
    #         text_size: sizes.Size | str = sizes.text_lg, #change fontsize to default size
    font=["IBM Plex Sans", "ui-sans-serif", "system-ui", "sans-serif"],  # update font
    font_mono=["IBM Plex Mono", "ui-monospace", "Consolas", "monospace"],  # update font
).set(
    # Colors
    background_fill_primary="*neutral_100",  # Coolgray10 background
    background_fill_primary_dark="*neutral_950",  # Coolgray95 background for dark mode
    slider_color="*primary_600",  # Blue60
    slider_color_dark="*primary_500",  # Blue50
    # Shadows
    shadow_drop="0 1px 4px 0 rgb(0 0 0 / 0.1)",
    shadow_drop_lg="0 2px 5px 0 rgb(0 0 0 / 0.1)",
    # Block Labels
    block_background_fill="white",
    block_label_background_fill="white",  # same color as blockback gound fill
    block_label_radius="*radius_md",
    block_label_text_size="*text_md",
    block_label_text_weight="600",
    block_label_text_color="black",
    block_label_text_color_dark="white",
    block_title_radius="*block_label_radius",
    block_title_background_fill="*block_label_background_fill",
    block_title_text_weight="600",
    block_title_text_color="black",
    block_title_text_color_dark="white",
    block_label_margin="*spacing_md",
    # Inputs
    input_background_fill="white",
    input_background_fill_dark="*block-background-fill",
    input_border_color="*neutral_100",
    input_shadow="*shadow_drop",
    input_shadow_focus="*shadow_drop_lg",
    checkbox_shadow="none",
    # Buttons
    shadow_spread="6px",
    button_primary_shadow="*shadow_drop_lg",
    button_primary_shadow_hover="*shadow_drop_lg",
    button_primary_shadow_active="*shadow_inset",
    button_secondary_shadow="*shadow_drop_lg",
    button_secondary_shadow_hover="*shadow_drop_lg",
    button_secondary_shadow_active="*shadow_inset",
    checkbox_label_shadow="*shadow_drop_lg",
    button_primary_background_fill="*primary_600",
    button_primary_background_fill_hover="*primary_500",
    button_primary_background_fill_hover_dark="*primary_500",
    button_primary_text_color="white",
    button_secondary_background_fill="white",
    button_secondary_background_fill_hover="*neutral_100",
    button_secondary_background_fill_dark="*neutral_800",  # Secondary cool gray 80
    button_secondary_background_fill_hover_dark="*primary_500",
    button_secondary_text_color="*neutral_800",
    button_cancel_background_fill="*button_secondary_background_fill",
    button_cancel_background_fill_hover="*button_secondary_background_fill_hover",
    button_cancel_background_fill_hover_dark="*button_secondary_background_fill_hover",
    button_cancel_text_color="*button_secondary_text_color",
    checkbox_label_background_fill_selected="*primary_200",
    checkbox_label_background_fill_selected_dark="*primary_500",
    checkbox_border_width="1px",
    checkbox_border_color="*neutral_200",
    checkbox_background_color_dark="*neutral_700",  # Jan 18 test to fix checkbox, radio button background color
    checkbox_background_color_selected="*primary_600",
    checkbox_background_color_selected_dark="*primary_500",
    checkbox_border_color_focus="*primary_600",
    checkbox_border_color_focus_dark="*primary_500",
    checkbox_border_color_selected="*primary_600",
    checkbox_border_color_selected_dark="*primary_500",
    checkbox_label_text_color_selected="black",
    # Borders
    block_border_width="1px",  # test example border
    panel_border_width="1px",
    # Chatbubble related colors
    # light
    # color_accent = "*secondary_400",
    border_color_accent_subdued="*color_accent_soft",  # chatbubble human border color, use Blue 20 as an accent color
    color_accent_soft="*secondary_200",  # chatbubble human color
    # darkmode
    # chatbubble human border color in darkmode, use Blue 20 as an accent color
    border_color_accent_subdued_dark="*secondary_500",
    color_accent_soft_dark="*secondary_500",  # chatbubble human color in dark mode
    # Chatbot related font
    chatbot_text_size="*text_md",  # make it larger
    # additional dark mode related tweaks:
    # block_background_fill_dark="*neutral_950", # Jan 18 test coolgray95 background for dark mode
    block_label_background_fill_dark="*neutral_800",  # same color as blockback gound fill
    block_title_background_fill_dark="*block_label_background_fill",
    # input_background_fill_dark="*neutral_800", #This attribute help match fill color cool gray 80 to match background
    #                                             however cause the problem for the general theme.
    #  input_shadow_dark="*shadow_drop", #Test if it could make the border without the color
    # input_border_color_dark="*neutral_200",#add attribute for border Jan 18
    checkbox_border_color_dark="*neutral_600",  # Jan 18 test to fix border
)
