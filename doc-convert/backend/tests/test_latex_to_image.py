import unittest
from io import BytesIO

from PIL import Image

from converters.latex_to_image import render_latex_png


class LatexToImageTests(unittest.TestCase):
    def test_supported_worksheet_formulas_render_nonempty_pixels(self):
        formulas = (
            r"x^2 + \dfrac{1}{2} + \sqrt{y}",
            r"\boldsymbol{\dfrac13}",
            r"\text{原式}=x^2+4x+4",
            (
                r"\begin{align*}"
                r"a^2+b^2&=(a+b)^2-2ab\\"
                r"&=5^2-2\times3\\"
                r"&=25-6=\boldsymbol{19}"
                r"\end{align*}"
            ),
        )

        for formula in formulas:
            with self.subTest(formula=formula):
                image = Image.open(BytesIO(render_latex_png(formula))).convert("RGBA")
                self.assertIsNotNone(image.getchannel("A").getbbox())

    def test_unsupported_formula_falls_back_to_visible_source(self):
        image = Image.open(BytesIO(render_latex_png(r"\unsupported{value"))).convert("RGBA")
        self.assertIsNotNone(image.getchannel("A").getbbox())


if __name__ == "__main__":
    unittest.main()
