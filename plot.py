import matplotlib.pyplot as plt

# Data
models = ["GBOX", "mobile-use", "AutoGLM-Mobile", "LX-GUIAgent", "DroidRun", "Finalrun"]
success_rates = [86.2, 84.5, 80.2, 79.3, 78.4, 76.7]

# Style configuration
plt.style.use("dark_background")
fig, ax = plt.subplots(figsize=(9, 5))
bar_colors = ["#C084FC" if model == "GBOX" else "#8B5CF6" for model in models]  # brighter purple for GBOX
text_color = "#E0E0E0"  # light gray for readability

# Plot bars
bars = ax.bar(models, success_rates, color=bar_colors)

# Labels and title
ax.set_title("AndroidWorld Benchmark Success Rates", fontsize=14, color=text_color, pad=15, fontweight="bold")
ax.set_xlabel("Agent", fontsize=11, color=text_color, labelpad=10)
ax.set_ylabel("Success Rate (%)", fontsize=11, color=text_color, labelpad=10)
ax.set_ylim(70, 90)

# Rotate x labels to prevent overlap
plt.xticks(rotation=25, ha='right', fontsize=10)

# Aesthetic adjustments
ax.tick_params(colors=text_color)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["bottom"].set_color("#333")
ax.spines["left"].set_color("#333")

# Annotate bars
for bar in bars:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f"{bar.get_height():.1f}",
            ha="center", va="bottom", color=text_color, fontsize=10, fontweight="medium")

plt.tight_layout()
plt.show()
