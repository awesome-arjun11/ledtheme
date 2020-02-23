from syskaled.syskaled import RGB
import numpy


class ImageSourceBase():
    """ Abstract Base class for theme color image source"""
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @staticmethod
    def get_dom_color_from_image(img):
        """ Extracts most dominant color from image
        :param img: PIL Image object
        :returns RGB object representing r,g and b values
        """
        img = img.resize((150, 150), resample=0)
        pixels = img.getcolors(150 * 150)
        sorted_pixels = sorted(pixels, key=lambda t: t[0])
        dominant_color = sorted_pixels[-1][1][:3]
        return RGB(*dominant_color)
        
    @staticmethod
    def get_avg_color_from_image(img):
        """ Extracts average color from image
        :param img: PIL Image object
        :returns RGB object representing r,g and b values
        """
        avg_color_per_row = numpy.average(img, axis=0)
        avg_color = numpy.average(avg_color_per_row, axis=0)
        rgb = list(map(lambda x: int(x), avg_color))
        return RGB(*rgb)

        

    def get_theme_color(self):
        raise NotImplementedError("get_theme_color() should return a RGB(r,g,b) object")
