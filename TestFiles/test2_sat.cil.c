/* Generated by CIL v. 1.7.3 */
/* print_CIL_Input is true */

void sassert(int X ) 
{ 


  {
  return;
}
}
extern int ( /* missing proto */  assert)() ;
int main(void) 
{ 
  int i ;
  int x ;
  int y ;

  {
  y = 7;
  x = 0;
  if (y == 7) {
    x = 5;
    i = 1;
    {
    while (1) {
      while_continue: /* CIL Label */ ;
      if (i < 100000) {

      } else {
        goto while_break;
      }
      y = y + 1;
      i = i + 1;
    }
    while_break: /* CIL Label */ ;
    }
    {
    assert(x != 5);
    }
  } else {

  }
  return (0);
}
}
