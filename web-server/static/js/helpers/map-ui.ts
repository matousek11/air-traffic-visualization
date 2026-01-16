import L from "leaflet";
import "leaflet-rotatedmarker";
import type {Flight, Position} from "../types/flight";
import {FlightSimulation} from "../objects/flight-simulation";

export class MapUi {
    private map: L.Map;
    private flightSimulation: FlightSimulation;
    // Store references to markers and polylines for cleanup
    private flightMarkers: Map<string, L.Marker> = new Map();
    private flightPolylines: Map<string, L.Polyline[]> = new Map();
    private planeIcon: L.Icon;
    private updateIntervalId: number|null = null;

    constructor() {
        this.map = L.map('map').setView([49.9, 14.0], 13);
        this.flightSimulation = new FlightSimulation();

        // Dark tile layer (Carto)
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(this.map);

        this.planeIcon = L.icon({
            iconUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAgAAAAH+CAYAAADqCLYOAAAACXBIWXMAAAsTAAALEwEAmpwYAAAzkUlEQVR4nO3debhfVXno8e8JCYQghCBTAIFAVGSMEARERlEwJoiWoBYJ1hawDoCKrdB7EentBawDQ8ukDypqHbBXEQRUbKWRQUGGcMKgjDIFkEgYkkim+8d7fp4fIcMZ9t5r772+n+c5jyNr7eT8zlnvfte73tWzYMECJLXSesAuwPbADn3/ujGwDrA+MAYYDfwJmNf39SxwP3A3MLvvXx8GllX65JJK12MAILXGKGAv4KC+r92BkQWM+xTwc+BnfV9zChhTUmIGAFLz7Q7MAN4HbFjyXMuA3wJfB75NZAwkNZABgNRMawEfAj4OvCHRMywA/hO4CPhVomeQNEQGAFKzrAP8HfBpYPPEz9LteuCfgOtSP4ikgTEAkJqhB/ggcCZRyFdXVxGBwO2Jn0PSaoxI/QCSVuuNRIr9Euq9+ANMAW4GziGyFZJqygBAqq9RwBnALcCbEz/LYIwEjgduBd6S+FkkrYQBgFRP2wAzgc/Q3J/T1xE1Af9Cc/8MUmtZAyDVz7uAS4lGPm1xJXAk8FzqB5EUjMqlejmeOFrXpsUfYCpRG7Bd6geRFAwApHoYAXyZKJ5bI/GzlOV1xLbGLqkfRJIBgFQHPcD5wImJn6MKGwLXAjulfhApdwYAUnqfB45L/RAV2hD4BQYBUlIGAFJa/wKclPohEtiIuGBoy9QPIuXKAEBK5yjglNQPkdAmwOXEtcSSKmYAIKWxK3GJTu4mARenfggpR/YBkKq3CdHdb4uK5lsM/Jq4sOdO4F7gGeAFYAkwFtgA2Io4prcLcADlXy3c7RPA2RXOJ2XPAECq3uXAoSXPsZTYY/8GcDXw7CD/+RFEluJwYAYwvsiHW4GFRDbg3pLnkdTHAECq1pHAt0ocfyHwVeBfgT8UNOZIImD5LLBzQWOuyExgfyJ4kVQyAwCpOpsCvcCrSxh7GfBt4u6Ax0oYHyIrcDjwBeA1Jc3x98CFJY0tqYsBgFSdS4nK/6I9BPwN8MsSxl6R9YCziN4FPQWPPY/oGPhUweNKWo6nAKRq7EKk/4v2I2Kv/pcljL0yzxFv6n9FFBIWaSzwDwWPKWkFzABI1bgGOLjgMc8CTibS/6nsBFxBnCAoynxgW2BOgWNKWo4ZAKl8+1P84v8JYr8/5eIPcaxwf+DhAsccQ/zZJJXIAEAq36cKHu9/Ua8z8w8RfQOKLD48jmr7EEjZMQCQyrUtMKXA8S4k7g+omweJmoA/FzTeaOADBY0laQUMAKRyfZTifs5uAk4oaKwy/Br4WIHj/U2BY0lajkWAUnnWJArZxhUw1vNEwV2Re+1l+QnFZT12J9omSyqYGQCpPG+lmMUf4J9oxuIPcUTw+YLGmlHQOJKWYwAgleevChrnDuDfCxqrCn8AvlTQWEWfnpDUxy0AqRwjgScoppL9ncBVBYxTpbFEYWARGZAJxEkDSQUyAyCVYzeKWfx/S/MWf4iWvhcUNNZbCxpHUhcDAKkcby5onPMLGieFSyimUZEBgFQCAwCpHHsVMMZzwHcKGCeV+4H/KWCcNxYwhqTlGABI5SgiA3A10PQinSsKGGNb4kilpAIZAEjFGwdsXsA4PypgjNSuLWCMUUQQIKlABgBS8SYUNE4R6fPUZgHPFjDOGwoYQ1IXAwCpeEUEAI8CjxcwTmrLgLsLGKfI64YlYQAglWGbAsaYVcAYdXFPAWOsV8AYkroYAEjF26iAMZrS9ncgirgmeN0CxpDUxQBAKt7oAsZ4tIAx6qKIewHGFjCGpC4GAFLx1i5gjBcLGKMuiggAXlXAGJK6GABIxRtTwBgvFTBGXSwpYIw1ChhDUhcDAKl4owoYo4hFU5JWygBAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIkpQhAwBJkjJkACBJUoYMACRJypABgCRJGTIAkCQpQwYAkiRlyABAkqQMGQBIxXoVsGXqh2ihLYm/W0kFMQCQivMOoBfYI/WDtNAewL3Au1M/iNQWBgDS8G0AXARcBWyV+FnabDPg/wHfBzZO/CxS4xkASMMzHbgHODb1g2Sk+++8J/GzSI1lACANzQTgGuJtdKPEz5KjcUTW5b+B1yV+FqmRDACkwVkD+CSx139wifO8WOLYVZtf4tj7AbcR35M1SpxHah0DAGngdgZuAL4IjCl5rgdLHr9KD5c8/hjie3ILMLnkuaTWMACQVm9t4Azgt8CbKpjvJeDuCuapymziz1S2SUSAdgbxPZO0CgYA0qrtA9wKfAYYWdGcPwT+VNFcVZgL/LiiuUYR36te4KCK5pQayQBAWrFxwFeA64DtKpx3EfCFCueryueBxRXOtw3wM+J7uH6F80qNYQAgvdI0YBbwd1R/zOyzxF5229wMnF7xnD3E9/AeYEbFc0u1ZwAg9RsPXEakq7dIMP+5wFkJ5q3K/wE+ByyreN5NgG8AVwCvqXhuqbYMAKR4U/wwUXh3eIL5nwHeB5wALE0wf1WWAacB7yf+zFWbCtxJfK9tIKTsGQAodxOBa4ELgLEJ5r8M2B74XoK5U/ke8Frg4gRzjyW+1zOJv3cpWwYAytUo4B+JN8IDE8z/OHGxzRHAUwnmT+1PwHHAFMrvE7AiewO3A2cCayWYX0quZ8GCBamfQaraG4GvArsmmHtp39wnAc8nmL+OxgCnEn8nKbr59QLHADclmFtKxgyAcjKGeOO7mTSLfy/x5nkcLv7d5hNn93cnei5UbUeigdBFwLoJ5peSMABQLt4B3EWk/at+y1xEVPdPxrfMVbkN2IMIBhZWPHcPcbvgPcTWjNR6bgGo7TYgWsOmuq73eiK93KbWvlWYSLyRp6jPgCjO/Bh51mcoE2YA1Gbd98ZXbR5wIrAvLv5DcR/RyvdoopVw1bo/Ox4ZVCuZAVAbTSCOepV5Xe+qXAl8BHgk0fxtsylwHml6NEC0gz4W+F2i+aVSmAFQm4wgflHPIs3iP4d4Y52Gi3+R5hBv5IcCjyaYfz/iyGCK+hGpNGYA1BY7Exe/VHFd7/KWAd8CPkGaDnc5GUvcKfAx0rzA3E7UdLTxvgZlxgyAmm400V72ZtIs/vcDbycum3HxL988omXyfsQefdUmATcC5wDrJJhfKowZADXZPkQ72Sqv6+1YDJwPnAK8mGB+RfD3GeBkYM0E8z9A9HS4NsHc0rAZAKiJ1idulTMNLICdiO6Kbv9Ig+AWgJpmGtG//3iq//wuIN44J+PiXyd3AnsRb+MvVDx3D3AUMJvYBpIawwyAmmI8cRTsrxLN71GwZtgauBCPgEqrZQZAdddDvFn1kmbx79xadwAu/k3wEHAIccvi0wnmn0p8Vk/A36+qOTMAqrOJRJHfAYnmtx1ss40jLn9K2Qb6WOIOCql2jFBVR6OIpiu9pFn8HycuhDkCF/8m62RvpgAPJ5h/b6Jg9ExgrQTzS6tkBkB1syvR0CfFdb1LiWryk/C63rYZA5xKfG9TdPPrJU6OeBukasMMgOpiDPGm9BvSLP69xBvbcbj4t9F84gTH7sCtCebfEbiBuOFw3QTzS69gAKA6eAexT5qi1/oi4CziaJ9vZ+13G7AHEQwsrHjuHqIm4B5ii0lKyi0ApbQBcAZpi7SOwet6czWReCM/MNH8FpkqKTMASmU6cC9pFv95wInAvrj45+w+4CDiBse5CeafTmQDjiWyA1KlzACoahOIRi1vTzS/jVq0IpsSjaYOTzS/jaZUOTMAqsoI4hfcLNIs/nOIN71puPjrleYQb+SHAo8mmH8/4shgijoYZcoMgKqwM3G0z8ta1ARjgdPxsim1nBkAlWk0cBpwM2kW//uJbMMMXPw1cPOIVr77EXv0VZsE3AicA6yTYH5lwgyAyrIP0cZ3uwRzLwbOB04BXkwwv9pjNHFk8GRgzQTzP0D0prg2wdxqOQMAFW194HOYPlW77ER0iXQbS63hFoCKNI24m/14qv9sLSDe1Cbj4q/i3QnsRbyNv1Dx3D3AUcBsYjtLKoQZABVhPHGEKsV1veARKlVra+Io68GJ5vcoqwphBkDD0UO8kfSSZvHv3PZ2AC7+qs5DwCHEbZFPJ5h/KvEzdwL+DtcwmAHQUE0kivxSXNcLtlFVPYwjLrFK2c76WOIuDWlQjB41WKOIZiW9pFn8HycuUjkCF3+l18lCTQEeTjD/3kTh65nAWgnmV4OZAdBg7Eo09ElxXe9Sogr7JLyuV/U0BjiV+Iym6ObXS5yA8VZLDYgZAA3EGOIN4zekWfx7iTed43DxV33NJ06i7A7cmmD+HYEbiBsO100wvxrGAECr8w5ifzFFj/JFwFnE0T7fatQUtwF7EMHAworn7iFqAu4BDqt4bjWMWwBamQ2AM0hb3HQMXterZptIvJEfmGh+i2W1UmYAtCLTgXtJs/jPA04E9sXFX813H3AQcRPl3ATzTyeyAccS2QHpL8wAqNsEosFJiut6wQYnardNiYZZhyea34ZZehkzAIL4HBwLzCLN4j+HeEOahou/2msO8UZ+KPBogvn3I44MpqjnUQ2ZAdDOxNE+LzmRqjMWOB0vzVJCZgDyNRo4DbiZNIv//US2YQYu/srPPKKV737EHn3VJgE3AucA6ySYXzVgBiBP+xBtfLdLMPdi4HzgFODFBPNLdTOaODJ4MrBmgvnvBz4MXJtgbiVkAJCX9YHPYdpRqqOdiG6XbsepEm4B5GMacaf58VT/fV9AvOFMxsVfWpk7gb2IjpcvVDx3D3AU0XVzRsVzKxEzAO03njh6lOK6XvDokTQUWxNHcg9ONL9HcjNgBqC9eohIvpc0i3/nlrQDcPGXBush4BDi1sunE8w/lchInIDrRGuZAWiniUSRX4rresH2o1KRxhGXcdmWW4UysmuXUUSTj17SLP6PA+8m3lpc/KVidLJpU4CHE8y/N3AHEYSslWB+lcQMQHvsSlQQvzHB3MuIZkIn4XW9UpnGAKcSP2spuvn1EtkAb+dsATMAzTeGiMx/Q5rFvxd4M/GG4uIvlWs+caJmd+DWBPPvSGwJXASsm2B+FcgAoNmmAHeRprf3IuAs4mifbwNStW4D9iSCgYUVz925O+Qe4LCK51aB3AJopg2AM0hbFHQsEXxISmsi8UZ+YKL5LfptKDMAzTMduJc0i/9zwInAvrj4S3VxH3AQcaPm3ATzTyeyAccSx4/VEGYAmmMC0RgkxXW9YGMQqQnGA+cChyea38ZfDWIGoP46+22zSLP4P0m8WUzDxV+quyeIN/JDgUcTzL8fcedHirokDZIZgHrbmThe5+UgkgZrLHA6Xv6llTADUE9rA6cBN5Nm8X+AyDbMwMVfaqp5RCvf/Yk9+qpNAm4EzgHWSTC/VsMMQP3sQ7Tx3S7B3IuB84FTgBcTzC+pHKOJI4MnA2smmP9+4MPAtQnm1koYANTH+sS5+mNIU0l7O6brpLZzW1F/4RZAPUwjOuqlOEazgHgzmIyLv9R2s4C9iM6dL1Q8dw9wFPG7bkbFc2sFzACkNR44jzTX9YJHdqScTQAuAA5ONL9HixMzA5BGD/2tNFMs/p3bxQ7AxV/K1YPAIcTtnU8nmH8qcCdRqOhalIAZgOpNJIr8UlzXC7btlPRKdWgvfgxwd6L5s2TUVZ1RRHOMXtIs/o8D7yGifRd/Sd3mElnBKcDDCebfG7iDuNl0rQTzZ8kMQDX2Iipvd0gw97K+uU/C63olrd4Y4FTid0aKbn69RDbAW0ZLZgagXGOIiHYmaRb/XuDNRGTv4i9pIOYTJ4N2B25NMP+OxJbARcC6CebPhgFAeaYQN+al6Im9iOgpMBmjaElDcxuwJxEMLKx47s4dKPcAh1U8dzbcAijexsAXiPOuKVxP/OB4Xa+kokwk3sgPTDS/xcslMANQrOnAbNIs/s8BJwL74uIvqVj3AQcRN4POTTD/dCIbkKJZWmuZASjGBOBC0lzXCzbUkFSd8cC5wOGJ5reBWUHMAAzPSKKJxSzSLP5PEhH5NFz8JVXjCeKN/FDg0QTz70fcXZKivqpVzAAMnZdqSMrdWOB0Yn8+xQvl7XiJ2ZCZARi8tYHTgJtJs/g/QGQbZuDiLymteUQWdH9ij75qk4AbgXOAdRLM32hmAAZnH6KN73YJ5l4MnA+cAryYYH5JWpXRxJHBk4E1E8x/P/Bh4NoEczeSAcDArE+cqz+GNBWot2OaS1IzuD3aEG4BrN40oqNeiuMnC4iIejIu/pKaYRbR/vw44IWK5+4hjmH3EtukWgUzACs3HjiPNNf1gkddJDXfBOAC4OBE83tEehXMALxSD/0tKFMs/n8iIucDcPGX1GwPAocQt5A+nWD+qcCdRKGi691yzAC83ESiyC/Fdb1gu0tJ7bUBcAbxgpXC9UQt1d2J5q8dI6Iwimgq0Uuaxf9x4D1ElOziL6mN5hLZzSnAwwnm3xu4g7ihda0E89eOGYAoVvkKaa7rXdY390l4Xa+kfIwBTiV+96Xo5tdLZAOyvi015wzAGCISnEmaxb8XeDMREbv4S8rJfOKE0+7ArQnm35HYErgIWDfB/LWQawAwhdgHStFLehHRU2AymUefkrJ3G7AnEQwsrHjuEfQXfB9W8dy1kNsWwMbAF0hzXS9ExHksXtcrScubSLyRH5ho/uyKsHPKAEwHZpNm8X8OOBHYFxd/SVqR+4CDiBtO5yaYfzqRDUjR9C2JHDIAE4ALSXNdL9iIQpIGazxwLnB4ovmzaMTW5gzASKL5wyzSLP5PEpHsNFz8JWkwniDeyA8FHk0w/37EHSwp6sQq09YMwM7AV4kK06p5GYUkFWcscDqxP5/ipfV2WnoZW9syAGsDpwE3k2bxf4DINszAxV+SijCPyObuT+zRV20ScCNwDrBOgvlL06YMwD5EU53XJ5h7MXA+cArwYoL5JSkHo4kjgycDayaY/37gw8C1CeYuXBsCgPWJc/XHkKZy83Zamh6SpJramXjhe1OCuVuzzdv0LYBpREe9FMc2FhCR6GRc/CWpSrOINu7HAS9UPHcPcZy8l9jubaymZgDGA+eR5rpeyOSIiCQ1wATgAuDgRPM39qh30zIAPfS3bkyx+P+JiDgPwMVfkurgQeAQ4jbVpxPMPxW4kyhUbNSa2qQMwETgYtJc1wsZtomUpIbZADiDeFFM4XqiJuzuRPMPShOilVFEM4Ze0iz+jwPvIaJLF39Jqq+5RJZ2CvBwgvn3Bu4gbppdK8H8g1L3DMBeRKVniut6l/XNfRJe1ytJTTMGOJX4HZ6im18vkQ2o7a2vdc0AjCEiqJmkWfx7gTcTkaSLvyQ1z3zipNbuwK0J5t+R2BK4CFg3wfyrVccAYAqxf5KiB/MioqfAZGoctUmSBuw2YE8iGFhY8dwj6C9cP6ziuVerTlsAGwNfIM11vRCR2rF4Xa8ktdVE4o38wETz16qYvC4ZgOnAbNIs/s8BJwL74uIvSW12H3AQcVPr3ATzTyeyASma171C6gzAtsCFxDckhcuBjwKPJZpf+dgZeCdRJbxp33/3e+C/ge8Dz6Z5rGTGEb8MDyTeyiCugL0B+AnR6U0q0+bAvwPvSjT/z4h7BR5MNH+yAGAk8db9OaLgr2pPAMcDP0gwt/KxBfB+4ANEALAyc4H/C3wZWFrBc6U0guihfgpxZntlZhH91r9DmvvglY/DgXOJDrNVexH4333zL6l68hQBwM7AV0lzXW9rLnFQba1HFPtMJ7qTjRzEP/ufRLBQdaFSVdYEvk4ERQO1lLiK9TLiZ9efW5VhLHA6sT+fYmv8dhJcKldlALA2cBrwSQb3S7Eovyf2XX6ZYG612yhisT8SOJT4rA/VRURasI0uJn7JDdUC4MfAt4FriFM7UpH2Jz6nr00w9yKiEP50KnoJqCoAOJD4xTZxdf/HEiwCvkj8pdbmyINaYU/ijf29wIYFjbmMuNTk5wWNVxcHA1dTXOHTH4HvEVkBj+yqSGsTDYQ+RQT3VavsZbXsAGB94lz9MaSpeLydBGkVtdqWRAr7Q8DrSprjp0RGoU2uBd5a0th/IGoFLsFLulScnYlusG9KMHcl29VlBgBHEIUNm5Q1wSrMJworziFBYYVaZ0PgfUSKf88K5ltCFBDOqWCuKmxGXJVaxd7qTcQWwXeJLIE0HGsQt/z9M+kK1j9O1AcVrowAYDxwHmmu6wW4jkif+Cag4RgNvI3oTfEuooCtSgfQnnqVg6h+S2MJccTym8Qvzxcrnl/tMgG4gNjKSuFK4CNEIF2YIiPyEcSZ+ntIs/g/QzR32B8Xfw3NCKJe5WvAk0TB2XSqX/wBtkowZ1k2TzDnGkTg8Q3iRs+vEd/bujQ/U7M8SGzLHU2akyhTgTuJAuHCttOL+mGYSOzx/RtxDKpqlwHbA5cmmFvNtwNxQuU+4BfAB0nzOe5W+6tEByH1n2U94nv6C+IN6hzgLSkfSI11KVH7c3GCuccSWYiZwBuKGHC4AcAo4tKeXiJlWbXHgfcQ9Qa16K2sxtic2Nu7hfj8fpZI86ndNiOagM0k2o+fht93Dc5c4qbYKcDDCebfG7iDuDF3WMH1cAKAvYhblob9EEOwjIjAtgN+WPHcaq71gBnAFcBDwNnAbgmfR2ltTwR+9wG/IgLCVyd9IjXJ1cRn6CyqLzbvvHzfwjAKk4cSAIwhFv2ZROq0ar3Am4kI7PkE86tZOnvBlxIZo28Q+2kpmlGpnkYQb1VnE22HryBd7YeaZT5xzfDuwK0J5t+RuMn2ImDdwf7Dgw0ApgB3E5HHGoOdbJgWEZHWZGz8odXbjdjrfZyoQD8KWCfpE6kJRhMB4veJY5iXEgFk8pvbVGu3EW/in6H6Vt4jiJNv9xBtyAf1Dw7EJsQPwk+IRihVux6YRPzl/jnB/GqGrYjg9F4iNXY8sHHSJ1KTjSMCx58TW0ZnUl7zJzVf5yV1J+C/Esy/GbEl/n0G+HtvIAHAdCLtftTQn2vIniNuDdwXuCvB/Kq/cUT0+yviqI6/pFWGLekPLmf3/fsUTc5Uf/cRWaOjiYLBqk0nsgHHsprM1aoCgI2IvbDvU1yf88G4nCiwOIf2X5GqwVmb6L9/BXFe/yJiD9c0raqwPRFoPkJ8Bt/L8C6AUvssI7LmOxNrWdXGEb8Xf8gqCltXFgDsQvTRn1r4Y63eE0QEcxjwWIL5VU8jiF7yXyP2Zr9LfD5TXNYhQXz2phKfxTnEZ/Ot2GxI/R6j/3rwJxLM/y5iLd9pRf/jij6oexAtNDcr75lWaBnwVSK6/kHFc6u+dgY+T1z4ci31aNIjLa/TbOha4rP6eeKzK0GsadsTa9yyiufegmgrPnn5/2H5AGArov3puPKf6WUeAN5O3Nz3bMVzq366m/TcAXyaNO1kpaHYnPjM3oHNhtTvWWKN24/Yo6/SBkTfgpd9DrsDgFHAj6i2anoRsZe2IxE5K1/rAX9DVM/+geY26VmKF8+U4UWaWQvU3Wzov4jPuBmsvM0EdiXWvkUVzrsh0Tb/L9um3QHAp4mjdlW5nWjoczJQ2p3EqrXlm/RcQrSUbuIe6t3A54DXAlclfpY2uorIUJ5InLlumhHEZ/sSom25zYbytoBY+yYDv6lw3t2AT3b+Q+cX7SbA/6roAeYDnyL+4LdUNKfqZS/i4qg5NLtJzxPAl4hofnsi1ftAygdquUeJU0G79n19iTSFVcO1Fv3Nhh4jfhb2SvpESmUW8SL8KWJtrMKp9GX6OwHAiVRzjOU64I3ED27VvZOVVqdJz++AG4iro1McLx2uBUQa7VDibPinaOYbadPdRvzdbwHsQ9wN0sTW4BsSPws3EBfL2MciP0uINXFH4KcVzDeGaJLGCKIn+jElT/gM0RRhf2IBUB42Aj4G3Eh/J7XXpnygIVpMpKCPJH5hH0GkcBenfCgBURfwK+JukE2J79FVNPN7091s6EbiZ2ejpE+kKj0IHEKslc+UPNexwBqdfakyb8C6jEiPXlriHKqP0cA0+tOb5zGM26oSu4toP/0a4J3Af1Bdmk6DN5/4Hr2T2NY8jmgjXvWxqyLsSfzsPEFsk80AXpX0iVSVS4ks0MUlzrERsO8I4G0lTfAw8YN4BFH0ovbqbtLzJHGUdDrNbNLzIPDPxFXTOxC9veckfSINxVziF+hbgDcQ39MHkz7R0HQKZb9BBNQ2G8rDXCKAfSexlpbh4BHEnnyRlhE/eDthNXTb7UAUvt1Hs5v0PAt8kwiGtyWKZO5N+UAq1L3E93Qbovj4XJr5UtLdbOgRoiDyLSkfSKW7isign0XxdXOTRlBswUkvUdF4HM0syNHqbQH8A1G92kuccW5ik5OFRHeuw4h08QziF2sT08UauN8STaZeQ3zvf0D117cWYTOikGsm8bP4D8TPptpnPrEV+Rbid25RXj+C6BA0XJ1rECcDNxUwnuplLLFAXkGkUTtXXjbNUmJP+ERiAZhOXNTxUsJnUhovEd/76UTx4NHAlTTzdNJOxM/kw0RB5AmUW9elNG4ijr9+hmKC1nEjKeb89Z7ArQWMo/oYRVSkfoA48jY67eMMy2zgW0SB2B8SP4vqZx5ReHUpUYn/18TnfoeUDzUEI4hbMfcmTtz8mPjcX0O1HedUns7L9s+JbNZwrDeSYq5QbWJxjVZsN+Jt/31U2xa6aE8QJ1AuI96KpIH4A7F4nkkEANOJ7MDWCZ9pKEYTBdhHAH8ishuXAr/Aba42KGLN7RlZwCBqvq2IBf9vaeY5/Y4FxC+6bxIXXzTxLLjqY3bf1+lEbdNRwPuBdVM+1BCMI579KCLA+Q7RktieLJnzKEm+xhHNIH5FRJNNbdKzhCjeO5rIWNikR0Xrbja0MbEldhnNTKt3Nxua3ffvN0n6RErGACAv3U16ngQuIvYLi9gGqlqnSc8WxPG9S4EXkj6RcrCQCDCPIIoHm9xsaHsi8H8Mmw1lyQCg/UYQx0cuovlNeh4hCmBs0qM66G42NIEISH+f9ImGprvZ0FPEC8I0ok28WsxvcHs1uYCp27PEG5cFTKqzh4mA9CyaXUi7NvF7YzpxRfcPsJC2tQwA2mVz4HDil8+uiZ9lOP5MpCQvxXP6ap7f9n19krhrZQbwHpp35XWn2dDxxJbbZcTPpFdet4RbAM3X3aTnIeBsmrn4dzfp2YJIQV6Gi7+aq1OgOoMIzpvcbGh7ouvn77HZUGuYAWimNWj2m0U33yyUg+5mQ51M3dEUfxdL2bqbDXUa0pipaygDgGZp8t5iN/cWlbPHiIt8zqHZtTprAVP7vmw21EAGAPVnkx6pvWw2pGSsAagnm/RIebHZkCpnAFAfNumRBDYbUkUMANKySY+kVbHZkErjX34aTS786fYsNumRqmKzIRXKAKA6NumRVBSbDWnY3AIoV3eTnoexSY+kYtlsSENmBqB4NumRlMKKmg01MeNos6GKGAAUp8l7ct3ck5Oaz2ZDWi0DgOGxSY+kurPZkFbIGoDB2wCb9EhqHpsN6WUMAAamu0nPHNrRpGdzbNIj5cpmQzIAWIW2N+l5MukTSaoLmw1lyr+YV2pywUy3Z7FJj6TBsdlQRgwAQpOPzHSzSY+kothsqOVy3gKwSY/KYrZFbdL2ZkMbJn2ihHLLANikR5KGzmZDLZJLANDkvaxu7mVJqgubDTVcmwMAm/RIUjXa3Gzoa0S/gdZpWw2ATXokKZ02Nhu6h5Y2G2pDAGCTHkmqH5sN1VxTA4A2Nen5AzbpkdRuNhuqoaY9dJMLTbplVWgiSV1sNlQTTQgAmnzUpJtNeiTp5Ww2lFBdtwBs0iNJ+bDZUAJ1ygDYpEeSZLOhitQhAGjyHlC3Ru4BSVKNtbHZ0LPU5KK2VAGATXokSYOxomZD7wPWS/lQQ7A+/c2GHgH+g0TNhqqsAbBJjyRpuLqbDW1Cs5sNvYaEzYbKDgBs0iNJKovNhoahjADAJj2SpKrZbGiQihywyQUa3WzSI0nN1vZmQ7OLGHwksXc93EDgJuB1w3+cZDpppG8B11CTIxpqLINGqT46zYY+DbwD+ABRjT865UMNQXezod8VMN7ikcDzxBWIw9HExX8pcCMRTX0LeCbt46hFmljjIrXdS8QZ/MuJZnPvIt6s30Gk3ZukiDX32ZHEHsNwA4Am6SUW/P8gjmBIRTMDINVbd7Oh1wBHEpmBHVI+VMX+OIJYENvuceBcYB9gJ2JfyMVfZTEDIDXHI0T1/Y59X58DHkr5QBWZNQK4OfVTlOR5oorybcCWRD9mO/SpCmYApGaaDZwGTATeTqwhz6d8oBLdMoKoeG+L7iY9mwEf7PvPTbxQQs1lBkBqtiXEWfwPEicHmtxsaGV+PJL+9opN3vv4NfBt4LvA04mfRTIDILVH55TYFUQw8F6iXuBNKR9qmO4A7u00Ajo74YMMVadJz+uBPYHzcPFXPZgBkNrpKWKt2YPod9PUZkPnQH8nwG/SjGtrnwHOJ9oJb0385RdxHlIqkhkAqf06zYZeT6xJF9CM4+T3E6fg/hIA/Bk4MdXTrMZCYu/lXcS+/keBG/CXrCQpvWXEmvQRYo06jOjYtzDhM63K8cSa/7K7AK4AvpLkcV5pKXGhw4nAFsRFDz/GDn1qBrcApDx1mg1NJy4nOpootK9LIfoFwFWd/7B8C+DjiXOQe1X5RF1s0qM2MDslaUXNho4k1tgUbgA+0f1fLH8b4EKiLeJvqnoibNKj9jEDIKlbp9nQTqRpNnQbcf/Bn7v/yxVdBzwPeCvwnyU+zAJiX/9QYCts0iNJykOn2dC2xIvvxcBzJc53JXAAcdPty6woAAB4gdjD+ATFdUFaBPwEeD/wamJf/wriNkKpTdwCkLQ6S4kX3+OA8cBfE2tkUWvi88QafijxYv8KKwsAIH6JnQ1sD1zE0Csaf03UFmxOpCC+S2QAJEkSzAe+Q6yRmxNr5lC34hcAFwJvINbwlb6QLF8EuCKPAh8GPkt0QHo30XhnZXcpLyEW/Z8QRyE8py9J0sB0mg2dR1z7O50IDHZn5dcWLySut/8h8L2+MVZrIAFAx5NEsd65ff/c9sQRvQ2IlMVCoqjhbpYrNJAkSYP2O+Bf+r5GE2/1WwNrE8HAXKLA8C6GsHUwmACg22JgVt+XJEkq10Kimv+2ogZcVQ2AJElqKQMASZIyZAAgSVKGDAAkScqQAYAkSRkyAJAkKUMGAJIkZcgAQJKkDBkASJKUIQMASZIyZAAgSVKGDAAkScqQAYAkSRkyAJAkKUMGAJIkZcgAQJKkDBkASJKUIQMASZIyZAAgSVKGDAAkScqQAYAkSRkyAJAkKUMGAJIkZcgAQJKkDBkASJKUIQMASZIyZAAgSVKGDAAkScqQAYAkSRkyAJAkKUMGAJIkZcgAQJKkDBkASMXaDdivgHFeKmCMulhUwBj7AJMLGEdSHwMAqTiHA/8DbFrAWM8VMEZdPF/AGJsCM4EPFDCWJAwApCL0AP8IfA8YU9CYjxQ0Th08WtA4o4FLgTPxd5c0bD0LFixI/QxSk60NfA14b4FjLgPWA14ocMyU1gOeJQKlonwf+CDgLzBpiIyipaEbD/ySYhd/gFtpz+IPsZ0xq+AxjwBuALYseFwpGwYA0tDsBtwMvKmEsa8uYczUriphzElEEGBxoDQEBgDS4HWK/TYvYexlxD5321xC/NmKtjkWB0pDYgAgDVwPcCqx/1xUsd/yrgZ+X9LYKd0H/LSksTvFgZ+l2DoDqdUsApQGZjTwFcp901wK7E7UALTRLsSfrcwXjx8ARwPzS5xDagUzANLqjQeuo/w083m0d/EHuAM4v+Q5Dgeux+JAabXMAEirthtwOeXs93ebTRQUtv3NdQxRPLl9yfM8BhwG3FLyPFJjmQGQVm465RX7dZsDTKX9iz/En3Eq8GTJ82xOZG2OKHkeqbEMAKRX6nT2+y7lFft1zAHeDjxU8jx18iBwAMV1CFyZMcT30M6B0gq4BSC9XBmd/VamF5hGXot/twnAFcAOFcxl50BpOUbFUr+yOvutyDXAW8h38YfIBOwJ/LiCuewcKC3HAEAKuwA3UU5nv+WdS+yDz6tgrrp7AXgPcFYFc00CbiSOWkrZMwCQ4uhYFW+HLwF/C5wALCl5riZZAnyG+Lt5qeS5NiMKO+0cqOwZAChnZVzjuzLPAAcTLXG1YpcABwJPlTyP1wpLWASofFXR2a+jFziU2PPW6lVZHGjnQGXL6Fc5qqqzH/QX+7n4D1yVxYF2DlS2DACUm0lY7NcEFgdKJTMAUE6qetuz2K8YKYoDjyx5Hqk2DACUA4v9mq3K4sBvYnGgMmERoNrOYr/2sDhQKpBRrtpsMyz2axOLA6UCGQCorSYRhV0W+7WLxYFSQQwA1EYW+7WbxYFSAQwA1CYW++XlEuJaYYsDpSGwCFBtYbFfviwOlIbAaFZtUOUFLxb71Y/FgdIQGACo6SZRXaGWxX71ZXGgNEgGAGoyi/3UzeJAaRAMANREFvtpVSwOlAbAIkA1jcV+GiiLA6VVMGpVk1jsp8GwOFBaBQMANcUkLPbT4FkcKK2EAYCawGI/DYfFgdIKGACo7k4Fvk/5xX5PAwdhsV+bXUJ8j/9Y8jyd4sBTS55HGhaLAFVXPcCXibfxslnsl5cqiwMvBD4KLK1gLmlQzACors6mmsXfYr/8VFkc+GHgXyuYRxo0AwDV0THA8RXM80Us9stVpzjwixXM9UngQxXMIw2KWwCqm4nA7cA6Jc7xEvFm9rUS51BzfAi4AFizxDleAHYBHihxDmlQzACobr5EuYt/p7Ofi786qugc+CrgCyWOLw2aGQDVyR7ATSWOb7GfVqWK4sA9gN+UOL40YGYAVCcfL3Fsi/20OlUUB360xLGlQTEDoLp4FXEWf3QJY3+RuDzI5j4aiDWIzoGfKmHsBcCGeGeAasAMgOriQIpf/Dud/U7CxV8Dt4T4zJTROXBtYP+Cx5SGxABAdbF3wePZ2U/DVVbnwLcUPJ40JAYAqovtCxyrlyi2mlngmMrTTOBNxGeqKFV0IJRWywBAdbFZQeNY7KeiPQjsRXHFgeMLGkcaFgMA1cWrChjDa3xVlk7nwPMKGGtsAWNIw2YAoLoYWcAYX8diP5VnCfCNAsYp4rMuDZsBgCRJGTIAkCQpQwYAkiRlyL0oKT+b9H29uu8/zwXmAE8meyJJlTMAkNpvU+J0xEHEcbYtV/L/ewS4AbgWuJIICiS1lAGA1E47EIv+NGLRH8h232uA9/Z9AdxF3I53JXA9sKz4x5SUigGA1A6jiQZI04B3E4v5cG3f9/WPwFPAT4mA4GriXLykBjMAkJprQ2AK8aZ/MLBeiXNtDBzV97WAyAhcCfwAeKzEeSWVxABAapahpPaLtjZRT3AQcDZuFUiNZAAg1VsZqf2iuVUgNZABgFQ/Vab2i+ZWgdQQBgBSPdQhtV80twqkGjMAkNLoTu0fxsrP5reJWwVSjRgAqE16Uj/AajQ5tV80twqkxAwApHK1MbVfNLcKpAQMAKRi5ZjaL5pbBVIFDACk4TO1Xx63CqSSGABIQ2Nqv3puFUgFMgCQBsbUfv24VSANgwGAtHKm9pvDrQJpkAwA1CZFHAOcRH9qfzLtTu0/3fevGyV9iuJ1bxV8GbiF/q2C2xI+l1QrBgBqk6HsAeeW2n+AWAivAH4JLAXeSPz5pwK7Uv9+CoPRA+ze93U6bhVIf9GzYMGC1M8gAdwPbDPMMXYDbh3A/y+n1P4S4CZiwfsRcO9q/v9bA28nAoK3AWuV+GypDWWrYDciozAcDwDbDnMMadgMAFQXZQcAOVXtPwP8F7GwXQ7MG+I4Y4C30v/3Nr6Qp6uvgZwqMABQaxgAqC6KDgByT+0vLnj8EbR7q2B5K9sqMABQaxgAqC6KCADeSbylTiXS1+sM96Fq7CXgOvrfWB+seP4J9GcG9gPWrHj+Kr0IXEv8PT/R96/DYQCgWjAAUF3cDWyX+iFqrqjUftFy2yoYrruJ/gVSUgYAqosbgT1TP0QNzab/Lf8moqivztYgvo+dYGCHtI9TS7/Gz7pqwGOAqotH8JcivLxq/3LgnrSPM2hLiAK664GTyetUwUBVvV0jrZABgOriTmB66odI5I/AVcSi/zPgubSPU6iHgIv7vtajPxiYQhzHzNFdqR9AArcAVB/7EkVtueiu2r8OWJT2cSq3/KmC3dI+TqX2BWamfgjJAEB1MRJ4Etgg9YOU5CXgf+jfz38g7ePUzjb01w3sS3tPFTwNbE5+AZ9qyABAdfJl4MTUD1GgTmr/SuJMeZtS+2Vaj+jQOJX2bRWcQ7s+42owAwDVyTZEq9om16bMpj+134Sq/brrnCrobBU0+VTBIuB1RF2ElJwBgOrmXODjqR9iEEztV6vJWwX/RrM+22o5AwDVzQbALGKftK7+SLSHvQJT+yl1tgqmAe+g3lsFjwE7As8mfg7pLwwAVEf7Eh3v1kj9IF26L4q5EVP7dbMGcclTJztQp057i4EDsfJfNWMAoLqaAXyddBfONL0hT+62ph4NiJYBfwdckmh+aaUMAFRnfw+cR3WZAFP77ZRqq2AJ8BGiCZJUOwYAqrtDgG8Bry5pfFP7ealqq+CPwFHANSWNLw2bAYCaYBPidMB0hr8lsIjovNc5qmfVft62of+I4X7AqALG/B7wSeDxAsaSSmMAoCaZDJxC/LIezC/qZ3h5r/26XKOrehnLy+8qGEzWaTERVJ4B/Kb4R5OKZwCgJtoQOIw4LbAbUfA1pu9/WwI8QaT2bwB+gal9DV5nq+AAohHRrsTnrtOkahFwP3Ab8N9EoehT1T+mNHQGAGqLscQFM88Tb2NSGcYCS4nPmdRo/x8l5wfV8uC53AAAAABJRU5ErkJggg==',
            iconSize: [40, 40],
            iconAnchor: [20, 20]
        });
    }

    public startHeadOnScenario(): void {
        // remove flights from simulation then start new scenario
        this.flightSimulation.resetSimulation()
            .then(async () => await this.flightSimulation.headCollisionTestScenario())
            .then(() => setTimeout(() => this.startUpdateLoop(), 500));
    }

    private startUpdateLoop = (): void => {
        if (this.updateIntervalId !== null) {
            clearInterval(this.updateIntervalId);
        }

        this.updateFlights();
        this.updateIntervalId = setInterval((): void => {this.updateFlights();}, 5000);
    }

    private async updateFlights(): Promise<void> {
        let flights: Flight[] = await this.flightSimulation.updateFlights();
        this.clearAllFlights();
        flights.forEach((flight: Flight) => this.displayPlaneWithRoute(flight));
    }

    private clearAllFlights(): void {
        // Remove all markers
        this.flightMarkers.forEach((marker): void => {
            this.map.removeLayer(marker);
        });
        this.flightMarkers.clear();

        // Remove all polylines
        this.flightPolylines.forEach((polylines): void => {
            polylines.forEach(polyline => {
                this.map.removeLayer(polyline);
            });
        });
        this.flightPolylines.clear();
    }

    private displayPlaneWithRoute(flight: Flight): void {
        // Remove existing marker if it exists
        const existingMarker = this.flightMarkers.get(flight.flightID);
        if (existingMarker) {
            this.map.removeLayer(existingMarker);
        }

        // Remove existing polylines for this flight
        const existingPolylines = this.flightPolylines.get(flight.flightID);
        if (existingPolylines) {
            existingPolylines.forEach(polyline => {
                this.map.removeLayer(polyline);
            });
        }

        // Create new marker
        const rotationAngle = flight.planePosition.heading;
        const marker = L.marker(flight.planePosition.position, {
            icon: this.planeIcon,
            rotationAngle: rotationAngle,
            rotationOrigin: "center center"
        })
            .addTo(this.map)
            .bindPopup(`
                <h3>${flight.flightID}</h3>
                <ul>
                    <li><b>speed:</b> ${flight.planePosition.speed}kts</li>
                    <li><b>heading:</b> ${flight.planePosition.heading} degrees</li>
                    <li><b>height:</b> ${flight.planePosition.height} feet</li>
                </ul>
            `);

        this.flightMarkers.set(flight.flightID, marker);

        // Draw route
        const polylines: L.Polyline[] = [];
        flight.flightPositions.forEach((startPosition, key) => {
            if (flight.flightPositions[key + 1] === undefined) {
                return;
            }

            let endPosition: Position = flight.flightPositions[key + 1] as Position;
            const polyline = L.polyline([startPosition, endPosition], {
                color: 'white',
                weight: 3,
                opacity: 0.7
            }).addTo(this.map);

            polylines.push(polyline);
        });

        this.flightPolylines.set(flight.flightID, polylines);
    }
}