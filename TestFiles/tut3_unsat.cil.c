/* Generated by CIL v. 1.7.3 */
/* print_CIL_Input is true */

void sassert(int X ) 
{ 


  {
  return;
}
}
extern int ( /* missing proto */  assert)() ;
void main(void) 
{ 
  int x ;
  int y ;
  int k ;

  {
  k = 3;
  x = 0;
  y = 0;
  {
  while (1) {
    while_continue: /* CIL Label */ ;
    if (k > 0) {

    } else {
      goto while_break;
    }
    x = x + 1;
    y = y + 1;
    k = k - 1;
  }
  while_break: /* CIL Label */ ;
  }
  {
  while (1) {
    while_continue___0: /* CIL Label */ ;
    if (x > 0) {

    } else {
      goto while_break___0;
    }
    x = x - 1;
    y = y - 1;
  }
  while_break___0: /* CIL Label */ ;
  }
  {
  assert(y == 0);
  }
  return;
}
}
