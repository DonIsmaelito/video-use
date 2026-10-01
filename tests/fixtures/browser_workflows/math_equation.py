"""Two-second MathTex smoke scene compatible with Manim CE 0.19.

python -m manim render --renderer cairo --disable_caching -r 640,360 --fps 15 \
    --media_dir edit/math-proof tests/fixtures/browser_workflows/math_equation.py MathEquation

This is a dependency/geometry proof, not a template for educational films.
"""
from fractions import Fraction

from manim import (
    DOWN,
    RIGHT,
    UP,
    Indicate,
    MathTex,
    Rectangle,
    Scene,
    Text,
    TransformMatchingTex,
    VGroup,
    config,
)


class MathEquation(Scene):
    def construct(self):
        assert Fraction(1, 2) + Fraction(1, 4) == Fraction(3, 4)
        self.camera.background_color = "#131621"
        foreground, green, violet = "#F4F0E5", "#6DDBAF", "#BAA0FF"
        title = Text("A common denominator", font_size=28, color=foreground).shift(UP * 2.2)

        def equation(first):
            result = MathTex(first, "+", r"\frac{1}{4}", "=", r"\frac{3}{4}", font_size=66, color=foreground)
            result[0].set_color(green)
            result[2].set_color(violet)
            return result.shift(UP * .35)

        initial = equation(r"\frac{1}{2}")
        quarters = equation(r"\frac{2}{4}")
        blocks = VGroup(*[
            Rectangle(width=1.05, height=.65, stroke_width=2,
                      stroke_color=green if i < 2 else violet if i == 2 else "#586071",
                      fill_color=green if i < 2 else violet if i == 2 else "#131621",
                      fill_opacity=1)
            for i in range(4)
        ]).arrange(RIGHT, buff=.08).shift(DOWN * 1.4)
        for item in (title, initial, quarters, blocks):
            assert item.get_left()[0] > -config.frame_width / 2 + .4
            assert item.get_right()[0] < config.frame_width / 2 - .4
            assert item.get_top()[1] < config.frame_height / 2 - .4
            assert item.get_bottom()[1] > -config.frame_height / 2 + .4
        self.add(title, initial, blocks)
        self.wait(.2)
        self.play(TransformMatchingTex(initial, quarters), run_time=.8)
        self.play(Indicate(quarters[-1], color=foreground, scale_factor=1.08), run_time=.4)
        self.wait(.6)
