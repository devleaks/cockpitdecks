# Simple implementation of a reverse polish calculator in Python.
# Stolen here: https://github.com/scriptprinter/reverse-polish-calculator
# Added a few necessary functions
# Alternatively, the following package https://github.com/axiacore/py-expression-eval
# could be used to offer a more "classical" expression writer. Code needs adjustments.
# This one is soooo simple, so powerful and can easily be extended.
import math


class RPC:

    def __init__(self, expression):
        self.tokens = []

        if type(expression) != str:
            expression = str(expression)
            # print("RPC::__init__: expression is not a string")
            # try:
            #     self.tokens.append(float(expression))
            # except:
            #     self.tokens.append(expression)
            #     print("RPC::__init__: expression cannot be converted to a float")
            # return

        for part in expression.split(" "):
            try:
                self.tokens.append(float(part))
            except:
                self.tokens.append(part)

    def calculate(self, return_stack=False):
        stack = []

        for token in self.tokens:
            if isinstance(token, float):
                stack.append(token)
            elif token == "+":
                stack.append(stack.pop() + stack.pop())
            elif token == "-":
                number2 = stack.pop()
                stack.append(stack.pop() - number2)
            elif token == "*":
                stack.append(stack.pop() * stack.pop())
            elif token == "/":
                number2 = stack.pop()
                stack.append(stack.pop() / number2)
            elif token == "%" or token == "mod":
                number2 = stack.pop()
                stack.append(stack.pop() % number2)
            elif token == "floor":
                stack.append(math.floor(stack.pop()))
            elif token == "ceil":
                stack.append(math.ceil(stack.pop()))
            elif token == "round":  # round to integer
                stack.append(round(stack.pop(), 0))
            elif token == "roundn":  # round to integer
                number2 = stack.pop()
                stack.append(round(stack.pop(), int(number2)))
            elif token == "abs":  # absolute value
                stack.append(abs(stack.pop()))
            elif token == "chs":  # change sign
                stack.append(-1 * stack.pop())
            elif token == "eq":  # test for equality, pushes 1 if equal, 0 otherwise
                stack.append(1 if (stack.pop() == stack.pop()) else 0)
            elif token == "lt":  # test for <, pushes 1 if <, 0 otherwise
                stack.append(1 if (stack.pop() < stack.pop()) else 0)
            elif token == "gt":  # test for >, pushes 1 if >, 0 otherwise
                stack.append(1 if (stack.pop() < stack.pop()) else 0)
            elif token == "not":  # test for equality, pushes 1 if equal, 0 otherwise
                stack.append(0 if stack.pop() != 0 else 1)
            elif token == "inf":  # inf is used as a keyword to return a special value
                stack.append(math.inf)
            elif token == "cos":  # calculate cosine, input expected in degrees
                angle_in_degrees = stack.pop()
                angle_in_radians = math.radians(angle_in_degrees)
                stack.append(math.cos(angle_in_radians))
            elif token == "sin":  # calculate sine, input expected in degrees
                angle_in_degrees = stack.pop()
                angle_in_radians = math.radians(angle_in_degrees)
                stack.append(math.sin(angle_in_radians))
            elif isinstance(token, str):
                print(f"RPC: pushing string {token}")
                stack.append(token)
            else:
                print(f"RPC: invalid token {token}")

        return stack if return_stack else stack.pop()
