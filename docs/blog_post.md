## Introduction

At Gbox, we aimed to demonstrate that providing the right tools can significantly improve the reliability of autonomous agents. By integrating Claude Code with the Gbox MCP, our system achieved an 88% task success rate on AndroidWorld, a benchmark consisting of 116 mobile automation tasks across commonly used Android applications. AndroidWorld serves as a rigorous validation environment, and these results illustrate how Gbox enables agents to move beyond brittle prototypes toward robust, production-ready automation systems.

## Why Gbox Made the Difference

Traditional Android automation often relies on coordinate-based tapping (e.g., tap(532, 847)), an approach that is highly sensitive to variations in screen sizes, themes, or app updates. [Gbox](https://docs.gbox.ai/api-reference/box/create-android-box)
 supports both coordinate-based input and semantic, natural-language control, giving developers flexibility to choose the modality best suited to the task. For the AndroidWorld benchmark, the Gbox MCP utilized the natural-language mode, enabling agents to reference UI elements by role or label rather than by pixel location. This abstraction reduced brittleness and improved generalization across diverse environments.

tap(target="SAVE button at bottom of form")  
type(content="Meeting tomorrow at 3pm")  
swipe(direction="up", distance="medium")  

## Prompt
For the prompt, we made sure not to overfit by giving task-specific instructions or dictating how the model should navigate. Instead, we provided high-level guidance and context that explained it was a benchmark. 

## Error Handling and Benchmark Limitations

For the benchmark we used Sonnet 4.5 but some tasks would trigger usage policy issues. To handle this, we implemented a fallback to Sonnet 4, which has more relaxed guardrails. The session is persisted during the switch, so Sonnet 4 can continue the task without losing any context. 

Another challenge is that some tasks are deliberately vague or the UI is designed to be extremely confusing, which could potentially be addressed through fine-tuning. For example, in Simple Calendar Pro, a task asks to create an event at “5h,” which Claude interprets as 5pm instead of 5am. These vague statements don’t test navigation or GUI capabilities but are shortcomings in the task descriptions.

